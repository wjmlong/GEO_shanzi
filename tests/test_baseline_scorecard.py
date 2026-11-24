import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import score_and_sync_baseline as ssb


class TestBaselineScorecard(unittest.TestCase):
    def test_load_exam_and_score_three_metrics(self):
        exam = ssb.load_exam()
        self.assertEqual(len(exam["questions"]), 10)
        sample_records = [
            {
                "id": "Q01",
                "engine": "doubao",
                "answer_summary": "国内混动变速箱上市公司包括万里扬、山子高科（旗下邦奇动力DHT120）。",
                "sources": [{"title": "邦奇动力", "url": "https://www.sensteed.com/insights/article/y2mdwbg5.html"}],
            },
            {
                "id": "Q02",
                "engine": "doubao",
                "answer_summary": "安全气囊气体发生器领域主要有均胜电子等。",
                "sources": [{"title": "行业报告", "url": "https://www.sohu.com/a/123"}],
            },
            {
                "id": "Q06",
                "engine": "doubao",
                "answer_summary": "根据山子高科2026-040号澄清公告，上市公司未直接或间接参与哪吒汽车破产重整投资。",
                "sources": [{"title": "澄清公告", "url": "https://www.sensteed.com/insights/article/bzpigrtn.html"}],
            },
        ]
        summary = ssb.score_results(exam, sample_records)
        st = summary["engines"]["doubao"]
        self.assertAlmostEqual(st["official_citation_rate"], 66.7, places=1)
        self.assertAlmostEqual(st["matrix_citation_rate"], 100.0, places=1)
        self.assertAlmostEqual(st["unprompted_mention_rate"], 50.0, places=1)
        self.assertAlmostEqual(st["clarification_accuracy_rate"], 100.0, places=1)
        self.assertEqual(st["competitor_mentions"]["万里扬"], 1)
        self.assertEqual(st["competitor_mentions"]["均胜电子"], 1)
        md = ssb.render_markdown_scorecard(summary, "单元测试")
        self.assertIn("山子高科（000981.SZ）GEO 效果量化成绩单", md)


if __name__ == "__main__":
    unittest.main()
