from __future__ import annotations

import csv
import io
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from desktop_app.api import create_app
from desktop_app.main import _launch_workbench_window, _wait_for_relaunched_edge


class DesktopWindowLaunchTests(unittest.TestCase):
    def test_each_workbench_window_has_its_own_edge_profile(self) -> None:
        urls = ["http://127.0.0.1:50100", "http://127.0.0.1:50101"]
        profiles = []

        def start_browser(args, **_kwargs):
            profile_option = next(arg for arg in args if arg.startswith("--user-data-dir="))
            profile = Path(profile_option.split("=", 1)[1])
            self.assertTrue(profile.is_dir())
            self.assertIn(f"--app={urls[len(profiles)]}", args)
            profiles.append(profile)
            return Mock(wait=Mock(return_value=0))

        with (
            patch("desktop_app.main._find_workbench_edge", return_value=Path(__file__)),
            patch("desktop_app.main.subprocess.Popen", side_effect=start_browser),
            patch("desktop_app.main._wait_for_relaunched_edge", return_value=0) as wait_for_edge,
            patch("desktop_app.main.webbrowser.open") as default_browser,
        ):
            for url in urls:
                self.assertTrue(_launch_workbench_window(url, Mock(), logging.getLogger(__name__)))

        self.assertEqual(len(set(profiles)), len(urls))
        self.assertTrue(all(not profile.exists() for profile in profiles))
        self.assertEqual([call.args[0] for call in wait_for_edge.call_args_list], list(map(str, profiles)))
        default_browser.assert_not_called()

    def test_edge_relaunch_waits_for_the_matching_profile_window(self) -> None:
        profile = r"C:\Temp\workbench-profile"
        args = ["msedge.exe", f"--user-data-dir={profile}", "--app=http://127.0.0.1:50100"]
        regular_browser = Mock(info={"name": "msedge.exe"}, cmdline=Mock(return_value=["msedge.exe"]))
        workbench = Mock(info={"name": "msedge.exe"}, cmdline=Mock(return_value=args), wait=Mock(return_value=0))
        with patch("desktop_app.main.psutil.process_iter", return_value=[regular_browser, workbench]):
            self.assertEqual(_wait_for_relaunched_edge(profile), 0)
        regular_browser.wait.assert_not_called()
        workbench.wait.assert_called_once_with()

    def test_edge_failure_opens_default_browser_and_keeps_server_alive(self) -> None:
        url = "http://127.0.0.1:50100"
        server_thread = Mock(is_alive=Mock(side_effect=[True, False]))
        with (
            patch("desktop_app.main._find_workbench_edge", return_value=Path(__file__)),
            patch("desktop_app.main.subprocess.Popen", return_value=Mock(wait=Mock(return_value=1))),
            patch("desktop_app.main.webbrowser.open", return_value=True) as default_browser,
            self.assertLogs(logger=__name__, level="ERROR") as log,
        ):
            self.assertTrue(_launch_workbench_window(url, server_thread, logging.getLogger(__name__)))

        self.assertIn("Edge workbench window exited with code 1", log.output[0])
        default_browser.assert_called_once_with(url)
        server_thread.join.assert_called_once_with(timeout=1.0)


class DesktopAppApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_data_dir = os.environ.get("SHANZIGEO_DATA_DIR")
        self._tmp_dir = tempfile.TemporaryDirectory()
        os.environ["SHANZIGEO_DATA_DIR"] = self._tmp_dir.name

        self._browser_running_patcher = patch(
            "desktop_app.services.PortableBrowserEngine.is_running",
            return_value=False,
        )
        self._browser_running_patcher.start()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self._browser_running_patcher.stop()
        if self._prev_data_dir is None:
            os.environ.pop("SHANZIGEO_DATA_DIR", None)
        else:
            os.environ["SHANZIGEO_DATA_DIR"] = self._prev_data_dir
        self._tmp_dir.cleanup()

    def test_health_index_and_state_seeding(self) -> None:
        r_health = self.client.get("/api/health")
        self.assertEqual(r_health.status_code, 200)
        self.assertEqual(r_health.json(), {"ok": True})

        r_index = self.client.get("/")
        self.assertEqual(r_index.status_code, 200)
        self.assertIn("text/html", r_index.headers.get("content-type", ""))

        r_state = self.client.get("/api/state")
        self.assertEqual(r_state.status_code, 200)
        data = r_state.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["data_dir"], self._tmp_dir.name)
        self.assertFalse(data["browser_running"])

        # Seeded counts verification
        self.assertEqual(len(data["knowledge_bases"]), 3)
        self.assertEqual(len(data["titles"]), 36)
        self.assertEqual(len(data["keywords"]), 52)
        self.assertEqual(len(data["platforms"]), 9)
        self.assertGreaterEqual(len(data["ledger"]), 17)

        # Platform codes CH-01..CH-09
        codes = [p["code"] for p in data["platforms"]]
        self.assertEqual(codes, [f"CH-0{i}" for i in range(1, 10)])

        # Exam 10 standardized questions + 5 competitors
        self.assertEqual(len(data["exam_questions"]), 10)
        self.assertEqual(data["exam_questions"][0]["id"], "Q01")
        self.assertEqual(data["exam_questions"][-1]["id"], "Q10")
        self.assertEqual(len(data["competitors"]), 5)

        # Masked settings structure
        masked = data["settings_masked"]
        for key in (
            "llm_api_url",
            "llm_model_id",
            "has_llm_key",
            "official_endpoint_url",
            "official_key_id",
            "has_official_secret",
            "cdp_port",
        ):
            self.assertIn(key, masked)
        self.assertFalse(masked["has_llm_key"])
        self.assertFalse(masked["has_official_secret"])

        # Articles include content for editor selection
        self.assertGreater(len(data["articles"]), 0)
        self.assertTrue(data["articles"][0].get("content"))

    def test_csv_utf8_bom_export(self) -> None:
        resp = self.client.get("/api/ledger/export.csv")
        self.assertEqual(resp.status_code, 200)
        raw = resp.content
        # Must start with UTF-8 BOM (\xef\xbb\xbf)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

        decoded = raw.decode("utf-8-sig")
        reader = list(csv.reader(io.StringIO(decoded)))
        self.assertEqual(
            reader[0],
            ["序号", "发布平台", "目标AI引擎", "文章标题", "发布状态", "线上真实链接", "AI被翻牌次数", "更新时间"],
        )
        self.assertGreaterEqual(len(reader) - 1, 17)
        self.assertEqual(reader[1][0], "1")

    def test_assets_title_keyword_and_kb_crud(self) -> None:
        # 1. Title add, edit & delete
        r_add_t = self.client.post(
            "/api/assets/title",
            json={"library_id": 1, "title": "山子高科2026年先进封装材料业务进展深度拆解"},
        )
        self.assertEqual(r_add_t.status_code, 200)
        t_id = r_add_t.json()["id"]

        st1 = self.client.get("/api/state").json()
        self.assertEqual(len(st1["titles"]), 37)

        revised_title = "山子高科先进封装材料业务进展"
        r_put_t = self.client.put(f"/api/assets/title/{t_id}", json={"title": revised_title})
        self.assertEqual(r_put_t.status_code, 200)
        edited = next(t for t in self.client.get("/api/state").json()["titles"] if t["id"] == t_id)
        self.assertEqual(edited["title"], revised_title)
        self.assertEqual(edited["library_id"], 1)

        r_del_t = self.client.delete(f"/api/assets/title/{t_id}")
        self.assertEqual(r_del_t.status_code, 200)
        self.assertEqual(r_del_t.json()["deleted"], 1)
        st2 = self.client.get("/api/state").json()
        self.assertEqual(len(st2["titles"]), 36)

        # 2. Keyword batch add (comma + Chinese comma + newline) & delete
        r_add_kw = self.client.post(
            "/api/assets/keyword",
            json={"library_id": 1, "keyword": "邦奇DHT120, 艾尔希气体发生器，先进封装材料\n山子高科出海"},
        )
        self.assertEqual(r_add_kw.status_code, 200)
        kw_json = r_add_kw.json()
        self.assertEqual(kw_json["added"], 4)
        self.assertEqual(len(self.client.get("/api/state").json()["keywords"]), 56)

        r_del_kw = self.client.delete(f"/api/assets/keyword/{kw_json['ids'][0]}")
        self.assertEqual(r_del_kw.status_code, 200)
        self.assertEqual(len(self.client.get("/api/state").json()["keywords"]), 55)

        # 3. Official Knowledge Base manual edit
        r_put_kb = self.client.put(
            "/api/assets/kb/1",
            json={"name": "山子高科核心事实库（人工修订版）", "content": "山子高科（000981.SZ）旗下涵盖邦奇动力与艾尔希ARC。"},
        )
        self.assertEqual(r_put_kb.status_code, 200)
        self.assertTrue(r_put_kb.json()["ok"])

        kbs = {kb["id"]: kb for kb in self.client.get("/api/state").json()["knowledge_bases"]}
        self.assertEqual(kbs[1]["name"], "山子高科核心事实库（人工修订版）")
        self.assertIn("邦奇动力与艾尔希ARC", kbs[1]["content"])

    def test_manual_channel_is_available_for_dispatch_without_automatic_publish(self) -> None:
        channel = {"name": "官网合作方", "url": "https://example.org/editor", "notes": "编辑后台"}
        bad_url = self.client.post("/api/channels", json={**channel, "url": "javascript:alert(1)"})
        self.assertEqual(bad_url.status_code, 400)
        first = self.client.post("/api/channels", json=channel)
        self.assertEqual(first.status_code, 201)
        account_id = first.json()["id"]
        self.assertEqual(self.client.post("/api/channels", json=channel).status_code, 409)
        current = self.client.get("/api/state").json()
        platform = next(p for p in current["platforms"] if p["id"] == account_id)
        self.assertFalse(platform["is_official"])
        self.assertEqual(platform["editor_url"], channel["url"])
        existing = current["articles"][0]["id"]
        response = self.client.post("/api/dispatch", json={
            "mode": "existing", "article_id": existing, "account_ids": [account_id], "external_action": "publish",
        })
        self.assertEqual(response.status_code, 200)
        row = next(r for r in self.client.get("/api/state").json()["ledger"] if r["account_id"] == account_id)
        self.assertEqual(row["status"], "ready")
        self.assertFalse(row["url"])

    def test_receipt_saving_and_baseline_scorecard_recording(self) -> None:
        state0 = self.client.get("/api/state").json()
        pending_rows = [r for r in state0["ledger"] if r["status"] != "completed"]
        self.assertGreater(len(pending_rows), 0)
        target_ledger_id = pending_rows[0]["id"]
        live_toutiao_url = "https://www.toutiao.com/article/7488888888888888888/"

        # Save live URL receipt
        r_rec = self.client.post(
            "/api/ledger/receipt",
            json={"ledger_id": target_ledger_id, "url": live_toutiao_url},
        )
        self.assertEqual(r_rec.status_code, 200)
        self.assertTrue(r_rec.json()["ok"])

        state1 = self.client.get("/api/state").json()
        updated_row = next(r for r in state1["ledger"] if r["id"] == target_ledger_id)
        self.assertEqual(updated_row["status"], "completed")
        self.assertEqual(updated_row["url"], live_toutiao_url)
        self.assertEqual(updated_row["citations"], 0)

        # Record weekly baseline 3-metric run and verify citation increment on matching ledger URLs
        r_base = self.client.post(
            "/api/baseline/record",
            json={
                "engine": "doubao",
                "our_citation_rate": 70.0,
                "unprompted_rate": 60.0,
                "sensitive_accuracy": 100.0,
                "cited_urls": [
                    live_toutiao_url,
                    "https://www.sensteed.com/insights/article/keyinfo-304.html",
                ],
                "notes": "第1周真机联网回归测试",
            },
        )
        self.assertEqual(r_base.status_code, 200)
        base_json = r_base.json()
        self.assertTrue(base_json["ok"])
        self.assertGreaterEqual(base_json["matched_citations"], 2)

        state2 = self.client.get("/api/state").json()
        self.assertEqual(len(state2["citation_runs"]), 1)
        run = state2["citation_runs"][0]
        self.assertEqual(run["engine"], "doubao")
        self.assertAlmostEqual(run["our_citation_rate"], 70.0)
        self.assertEqual(run["notes"], "第1周真机联网回归测试")

        after_row = next(r for r in state2["ledger"] if r["id"] == target_ledger_id)
        self.assertEqual(after_row["citations"], 1)
        self.assertGreaterEqual(state2["summary"]["cited_urls"], 2)

    def test_dispatch_official_and_browser_modes(self) -> None:
        state0 = self.client.get("/api/state").json()
        by_code = {p["code"]: p["id"] for p in state0["platforms"]}
        official_id = by_code["CH-01"]
        toutiao_id = by_code["CH-02"]
        sohu_id = by_code["CH-03"]

        with (
            patch(
                "desktop_app.api.OfficialSitePublisher.publish_article",
                return_value={"ok": True, "remote_url": "https://www.sensteed.com/insights/article/post-test1.html"},
            ),
            patch.object(
                self.app.state.browser_engine,
                "publish_article",
                new=AsyncMock(
                    return_value={
                        "ok": True,
                        "status": "draft_saved",
                        "message": "今日头条已 0 Token 自动填好标题与正文并存草稿",
                        "url": "",
                    }
                ),
            ),
        ):
            r_disp = self.client.post(
                "/api/dispatch",
                json={
                    "mode": "upload",
                    "title": "山子高科邦奇动力混动DHT120量产技术解析",
                    "content": "# 邦奇动力混动技术\n\n严格依据定期报告披露数据撰写。",
                    "account_ids": [official_id, toutiao_id],
                    "external_action": "draft",
                },
            )
            self.assertEqual(r_disp.status_code, 200)
            res = r_disp.json()
            self.assertTrue(res["ok"])
            self.assertEqual(len(res["results"]), 2)
            self.assertEqual(res["results"][0]["status"], "completed")
            self.assertEqual(res["results"][1]["status"], "in_progress")
            art_id = res["article_id"]

        # Dispatch existing article in ledger_only mode without launching browser
        r_disp2 = self.client.post(
            "/api/dispatch",
            json={
                "mode": "existing",
                "article_id": art_id,
                "account_ids": [sohu_id],
                "external_action": "ledger_only",
            },
        )
        self.assertEqual(r_disp2.status_code, 200)
        res2 = r_disp2.json()
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["results"][0]["status"], "ready")

    def test_settings_ai_and_health_endpoints(self) -> None:
        r_cfg = self.client.post(
            "/api/settings",
            json={
                "llm_api_url": "https://api.example.com/v1",
                "llm_model_id": "deepseek-v4.1-flash",
                "llm_api_key": "test-llm-key-placeholder",
                "official_endpoint_url": "https://www.sensteed.com/insights",
                "official_key_id": "test-key-id",
                "official_secret": "test-secret-placeholder",
                "cdp_port": 9345,
            },
        )
        self.assertEqual(r_cfg.status_code, 200)
        self.assertEqual(self.app.state.browser_engine.cdp_port, 9345)
        self.assertTrue(r_cfg.json()["settings_masked"]["has_llm_key"])
        self.assertTrue(r_cfg.json()["settings_masked"]["has_official_secret"])

        # Submitting masked "***" preserves existing secrets
        self.client.post("/api/settings", json={"llm_api_key": "***", "official_secret": ""})
        st = self.client.get("/api/state").json()
        self.assertTrue(st["settings_masked"]["has_llm_key"])
        self.assertTrue(st["settings_masked"]["has_official_secret"])

        with patch(
            "desktop_app.api.AiComplianceAndWriterService.generate_article",
            return_value={"ok": True, "title": "测试母题", "content": "## 正文内容"},
        ):
            r_gen = self.client.post("/api/ai/generate", json={"topic_title": "测试母题", "style": "qa"})
            self.assertEqual(r_gen.status_code, 200)
            self.assertEqual(r_gen.json()["content"], "## 正文内容")

        with patch(
            "desktop_app.api.AiComplianceAndWriterService.inspect_article",
            return_value={
                "ok": True,
                "score": 91,
                "passed": True,
                "summary": "事实锚点清晰，符合信披规范",
                "dimensions": [{"name": "事实与公告一致性", "score": 92, "comment": "准确"}],
                "issues": [],
            },
        ):
            r_ins = self.client.post("/api/ai/inspect", json={"title": "测试母题", "content": "正文内容"})
            self.assertEqual(r_ins.status_code, 200)
            self.assertEqual(r_ins.json()["score"], 91)
            self.assertTrue(r_ins.json()["passed"])

        with patch(
            "desktop_app.api.OfficialSitePublisher.check_health",
            return_value={"ok": True, "service": "geoflow-agent"},
        ):
            r_oh = self.client.post("/api/official/health")
            self.assertEqual(r_oh.status_code, 200)
            self.assertTrue(r_oh.json()["ok"])

        with patch.object(
            self.app.state.browser_engine,
            "open_url",
            new=AsyncMock(return_value={"ok": True, "url": "https://www.doubao.com/chat/"}),
        ):
            r_bo = self.client.post("/api/browser/open", json={"platform": "doubao"})
            self.assertEqual(r_bo.status_code, 200)
            self.assertEqual(r_bo.json()["url"], "https://www.doubao.com/chat/")


if __name__ == "__main__":
    unittest.main()
