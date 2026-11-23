"""GEO 核心测试，只使用内存 SQLite，不联网。"""
import json
import sqlite3
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import yaml
import sentiment
from geo.analyze import analyze_answer, load_brand
from geo.report import build_geo_report
from geo.store_geo import migrate_geo, start_run, finish_run, insert_sample


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.brand = load_brand(Path(__file__).resolve().parents[1] / "geo/brand.yaml")

    def test_aliases_case_and_counts(self):
        result = analyze_answer("介绍：st银亿、山子高科、银亿股份、000981", self.brand)
        self.assertTrue(result["mentioned"])
        self.assertEqual(result["first_pos"], 3)
        self.assertEqual(result["mention_count"], 4)

    def test_numeric_boundaries(self):
        for text in ("1000981", "0009812", "10009812"):
            with self.subTest(text=text):
                self.assertFalse(analyze_answer(text, self.brand)["mentioned"])
        for text in ("000981", "代码：000981。", "A000981B"):
            with self.subTest(text=text):
                self.assertEqual(analyze_answer(text, self.brand)["mention_count"], 1)

    def test_domains_unique_in_order(self):
        result = analyze_answer("[来源](https://WWW.Example.com/a) https://other.org:443/b，"
                                "https://www.example.com/c https://other.org/d。", self.brand)
        self.assertEqual(result["domains"], ["www.example.com", "other.org"])

    def test_no_mention_and_sentiment(self):
        result = analyze_answer("看好", self.brand)
        self.assertFalse(result["mentioned"])
        self.assertIsNone(result["first_pos"])
        self.assertEqual(result["mention_count"], 0)
        self.assertEqual((result["score"], result["label"]), sentiment.score("看好")[:2])

    def test_competitors(self):
        self.brand["competitors"] = ["Acme", {"name": "其他公司", "aliases": ["Other"]}, "Acme"]
        self.assertEqual(analyze_answer("ACME other Acme", self.brand)["competitors"], ["Acme", "其他公司"])

    def test_question_bank(self):
        path = Path(__file__).resolve().parents[1] / "geo/questions.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(data["version"], 2)
        self.assertEqual(Counter(q["group"] for q in data["questions"]),
                         {"brand": 10, "category": 10, "holdout": 10})
        self.assertEqual(len({q["id"] for q in data["questions"]}), 30)
        for question in data["questions"]:
            self.assertIn(question["intent"], ("buyer", "educate", "probe"))
            self.assertTrue(question["text"])


class GeoStoreReportTests(unittest.TestCase):
    def setUp(self):
        network = patch("requests.sessions.Session.request", side_effect=AssertionError("禁止联网"))
        network.start()
        self.addCleanup(network.stop)
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        migrate_geo(self.db)
        self.run = start_run(self.db, question_version=1)

    def sample(self, group="brand", **fields):
        defaults = dict(engine="engine-a", question_group=group, mentioned=True,
                        first_pos=4, label="正面", domains_json=["example.com"])
        defaults.update(fields)
        return insert_sample(self.db, self.run, **defaults)

    def report_row(self, report, group, engine="engine-a"):
        return next(line for line in report.splitlines() if line.startswith(f"| {engine} | {group} |"))

    def test_migration_idempotent_and_run_lifecycle(self):
        sample_id = self.sample(raw_json={"正文": "内容"})
        migrate_geo(self.db)
        migrate_geo(self.db)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM geo_samples").fetchone()[0], 1)
        row = self.db.execute("SELECT raw_json FROM geo_samples WHERE id=?", (sample_id,)).fetchone()
        self.assertEqual(json.loads(row[0]), {"正文": "内容"})
        self.assertFalse(self.db.execute("SELECT name FROM sqlite_master WHERE name='posts'").fetchone())
        finish_run(self.db, self.run)
        self.assertIsNotNone(self.db.execute("SELECT finished_at FROM geo_runs").fetchone()[0])
        for table in ("geo_runs", "geo_samples"):
            self.assertIn("AUTOINCREMENT", self.db.execute(
                "SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0])

    def test_report_groups_and_errors(self):
        self.sample()
        self.sample(mentioned=False, first_pos=None, label="中性", error="")
        self.sample(error="失败", first_pos=999, label="负面", domains_json=["failed.org"])
        self.sample("category", label="负面", first_pos=8)
        self.sample("holdout", mentioned=False, first_pos=None, label="中性")
        report = build_geo_report(self.db)
        self.assertEqual(self.report_row(report, "brand"),
                         "| engine-a | brand | 2 | 1 | 50.00% | 4.00 | 1 | 1 | 0 |")
        self.assertIn("| 1 | 0 | 100.00% | 8.00 | 0 | 0 | 1 |", self.report_row(report, "category"))
        self.assertIn("| 1 | 0 | 0.00% | — | 0 | 1 | 0 |", self.report_row(report, "holdout"))
        self.assertIn("| example.com | 4 |", report)
        self.assertNotIn("failed.org", report)

    def test_only_errors_and_engine_separation(self):
        self.sample(error="timeout")
        self.sample(engine="engine-b")
        report = build_geo_report(self.db)
        self.assertIn("| 0 | 1 | 无有效样本 |", self.report_row(report, "brand"))
        self.assertIn("100.00%", self.report_row(report, "brand", "engine-b"))
        self.assertIn("无有效样本", self.report_row(report, "category"))

    def test_previous_run_delta_and_latest(self):
        self.sample()
        self.sample("category", error="timeout")
        old_run = self.run
        self.run = start_run(self.db, 2, "second")
        self.sample()
        self.sample(mentioned=False, first_pos=None)
        self.sample("category")
        report = build_geo_report(self.db)
        self.assertIn(f"run {self.run}", report)
        self.assertIn(f"较上一 run {old_run}", report)
        self.assertTrue(self.report_row(report, "brand").endswith("| -50.00 |"))
        self.assertIn("无法比较（无有效样本）", self.report_row(report, "category"))
        self.assertNotIn("较上一 run", build_geo_report(self.db, old_run))

    def test_domains_top_ten(self):
        self.sample(domains_json=[f"d{i}.org" for i in range(12)])
        self.sample(domains_json=["d11.org", "d11.org"])
        report = build_geo_report(self.db)
        self.assertIn("| d11.org | 2 |", report)
        domain_rows = report.split("| --- | ---: |\n")[1].strip().splitlines()
        self.assertEqual(len(domain_rows), 10)

    def test_empty_report_and_unknown_fields(self):
        self.assertIn("暂无运行记录", build_geo_report(self.db, 999))
        with self.assertRaises(ValueError):
            self.sample(unexpected="bad")
        self.db.execute("DELETE FROM geo_runs")
        self.assertIn("暂无运行记录", build_geo_report(self.db))


if __name__ == "__main__":
    unittest.main()
