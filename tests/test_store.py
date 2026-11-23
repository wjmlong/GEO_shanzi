"""只用内存数据库、临时 SQLite 文件、fixture 和 mock，禁止真实请求。"""
import copy
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import collector
import monitor
import store
from sentiment import score


def post(pid, top=0, comments=0, last=None):
    stamp = last or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return dict(post_id=pid, post_title="看好", user_id="u1", user_nickname="甲",
                post_publish_time=stamp, post_last_time=stamp, post_click_count=1,
                post_comment_count=comments, post_forward_count=0, post_type=0, post_top_status=top)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("禁止联网"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.db = collector.connect(":memory:")
        self.addCleanup(self.db.close)
        self.payload = json.loads((Path(__file__).parent / "fixtures/comments.json").read_text())
        self.args = SimpleNamespace(code="000981", hours=24, pages=10, content=0, proxy=False)

    def test_migration_compatible_and_wal(self):
        self.db.execute("INSERT INTO posts(post_id, content, llm_label) VALUES (1, '正文', '正面')")
        self.db.commit()
        store.migrate(self.db)
        self.assertEqual(self.db.execute("SELECT content, llm_label, comments_fetched_count FROM posts").fetchone(),
                         ("正文", "正面", 0))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            db = collector.connect(str(Path(directory) / "test.sqlite"))
            try:
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            finally:
                db.close()

    def test_legacy_migration(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("""CREATE TABLE posts(post_id INTEGER PRIMARY KEY, code TEXT,
                publish_time TEXT, content TEXT)""")
            db.execute("INSERT INTO posts VALUES(1, '000981', '2026-11-06', '保留')")
            db.commit()
            store.migrate(db)
            self.assertEqual(db.execute("SELECT content, comments_fetched_count, llm_label FROM posts").fetchone(),
                             ("保留", 0, None))

    def test_comment_upsert_idempotent(self):
        row = collector.parse_comments(self.payload, 1)[0]
        now = datetime(2026, 11, 6)
        self.assertTrue(store.upsert_comment(self.db, "eastmoney", row, score, now))
        row["like_count"] = 9
        self.assertFalse(store.upsert_comment(self.db, "eastmoney", row, score, now + timedelta(hours=1)))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM comments").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT like_count, first_seen_at, fetched_at, hits FROM comments").fetchone(),
                         (9, now.isoformat(), (now + timedelta(hours=1)).isoformat(), "看好"))
        self.assertTrue(store.upsert_comment(self.db, "other", row, score, now))

    def test_post_upsert_and_pending(self):
        p = post(1, comments=2)
        self.assertTrue(collector._upsert(self.db, "000981", p, score))
        self.assertFalse(collector._upsert(self.db, "000981", p, score))
        self.assertEqual(store.pending_comments(self.db, "000981"), [(1, 2)])
        self.db.execute("UPDATE posts SET comments_fetched_count=2")
        p["post_click_count"] += 1
        collector._upsert(self.db, "000981", p, score)
        self.assertEqual(store.pending_comments(self.db, "000981"), [])
        p["post_comment_count"] = 3
        collector._upsert(self.db, "000981", p, score)
        self.assertEqual(store.pending_comments(self.db, "000981"), [(1, 3)])

    def test_incremental_stop_and_top(self):
        pinned, old = post(1, top=1), post(2)
        for p in (pinned, old):
            collector._upsert(self.db, "000981", p, score)
        self.assertFalse(store.unchanged_post(self.db, pinned))
        changed = dict(old, post_last_time="2099-01-01 00:00:00")
        self.assertFalse(store.unchanged_post(self.db, changed))
        with patch.object(collector, "make_session"), patch.object(collector, "fetch_list",
                return_value=[pinned, post(3), old, post(4)]) as fetch:
            self.assertEqual(collector.collect(self.db, "000981", score, log=lambda x: None), 1)
        fetch.assert_called_once()
        self.assertIsNone(self.db.execute("SELECT 1 FROM posts WHERE post_id=4").fetchone())
        cursor = json.loads(self.db.execute("SELECT cursor_json FROM platform_state").fetchone()[0])
        self.assertEqual(cursor["000981"]["post_id"], 2)

    def test_changed_post_continues_paging(self):
        old = post(1, last="2026-01-01 00:00:00")
        collector._upsert(self.db, "000981", old, score)
        with patch.object(collector, "make_session"), patch.object(collector, "fetch_list",
                side_effect=[[post(1)], [post(2)], []]) as fetch:
            self.assertEqual(collector.collect(self.db, "000981", score, log=lambda x: None), 1)
        self.assertEqual(fetch.call_count, 3)

    def test_partial_failure_records_inserted_posts(self):
        with patch.object(collector, "make_session"), patch.object(collector, "fetch_list",
                side_effect=[[post(1)], collector.Blocked()]), redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()):
            self.assertFalse(monitor.run_once(self.db, self.args))
        row = self.db.execute("SELECT status, new_posts, new_comments, finished_at FROM crawl_runs").fetchone()
        self.assertEqual(row[:3], ("blocked", 1, 0))
        self.assertIsNotNone(row[3])
        self.assertTrue(store.is_blocked(self.db, "eastmoney"))

    def test_pages_upper_bound(self):
        with patch.object(collector, "make_session"), patch.object(collector, "fetch_list",
                side_effect=[[post(1)], [post(2)], [post(3)]]) as fetch:
            self.assertEqual(collector.collect(self.db, "000981", score, max_pages=2, log=lambda x: None), 2)
        self.assertEqual(fetch.call_count, 2)

    def test_backoff_doubles_caps_and_resets(self):
        now = datetime(2026, 11, 6)
        for minutes in (30, 60, 120, 240, 480, 720, 720):
            until = store.record_failure(self.db, "eastmoney", collector.Blocked(), now)
            self.assertEqual(until - now, timedelta(minutes=minutes))
        self.assertTrue(store.is_blocked(self.db, "eastmoney", now))
        self.assertFalse(store.is_blocked(self.db, "eastmoney", until))
        self.assertFalse(store.is_blocked(self.db, "other", now))
        store.record_success(self.db, "eastmoney", now)
        self.assertEqual(self.db.execute("SELECT consecutive_failures, blocked_until, last_error FROM platform_state").fetchone(), (0, None, None))
        self.assertEqual(store.record_failure(self.db, "eastmoney", "error", now) - now, timedelta(minutes=30))

    def test_blocked_skips(self):
        store.record_failure(self.db, "eastmoney", collector.Blocked())
        output = io.StringIO()
        with patch.object(monitor, "collect") as collect, redirect_stdout(output):
            self.assertFalse(monitor.run_once(self.db, self.args))
        collect.assert_not_called()
        self.assertIn("剩余", output.getvalue())
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0], 0)

    def test_runs_success_failure_and_status(self):
        with patch.object(monitor, "collect", side_effect=collector.Blocked()), redirect_stderr(io.StringIO()):
            self.assertFalse(monitor.run_once(self.db, self.args))
        self.assertEqual(self.db.execute("SELECT status, error FROM crawl_runs").fetchone(), ("blocked", "Blocked"))
        store.record_success(self.db, "eastmoney")
        with patch.object(monitor, "collect", side_effect=ValueError("坏响应")), redirect_stderr(io.StringIO()):
            self.assertFalse(monitor.run_once(self.db, self.args))
        store.record_success(self.db, "eastmoney")
        def collect(*args, **kwargs):
            collector._upsert(self.db, "000981", post(99), score)
        with patch.object(monitor, "collect", side_effect=collect):
            self.assertTrue(monitor.run_once(self.db, self.args))
        self.assertEqual(self.db.execute("SELECT status, new_posts FROM crawl_runs ORDER BY id DESC LIMIT 1").fetchone(), ("success", 1))
        for _ in range(5):
            store.finish_run(self.db, store.start_run(self.db, "other"), "success")
        output = io.StringIO()
        with redirect_stdout(output):
            monitor.print_status(self.db)
        self.assertEqual(sum(line.startswith("#") for line in output.getvalue().splitlines()), 5)
        self.assertIn("last_ok_at=", output.getvalue())

    def test_parse_comments_normal_and_stable(self):
        rows = collector.parse_comments(self.payload, 42)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["parent_comment_id"], rows[0]["comment_id"])
        self.assertIsNone(rows[0]["parent_comment_id"])
        self.assertEqual(rows[0]["content"], "看好")
        changed = copy.deepcopy(self.payload)
        changed["re"][1]["reply_like_count"] = 5
        changed["re"][1]["user_nickname"] = "新昵称"
        again = collector.parse_comments(changed, 42)
        self.assertEqual(rows[2]["comment_id"], again[2]["comment_id"])
        self.assertNotEqual(rows[2]["raw_hash"], again[2]["raw_hash"])
        self.assertEqual(collector.parse_comments({"re": []}, 42), [])

    def test_parse_comments_rejects_invalid(self):
        bad_child = copy.deepcopy(self.payload)
        bad_child["re"][0]["child_replys"] = {"x": []}
        bad_likes = copy.deepcopy(self.payload)
        bad_likes["re"][0]["reply_like_count"] = "many"
        for payload in (None, [], {}, {"re": None}, {"re": [{"code": "000981", "name": "山子高科"}]},
                        bad_child, bad_likes, {"re": [None]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                collector.parse_comments(payload, 1)


if __name__ == "__main__":
    unittest.main()
