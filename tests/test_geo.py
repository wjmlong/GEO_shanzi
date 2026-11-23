"""GEO 离线测试：只用内存数据库、fixture 和 mock。"""
import copy
import io
import json
import os
import sqlite3
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import monitor
import store
from geo import cli, store_geo
from geo.analyze import analyze
from geo.engines import DeepSeekEngine, DoubaoEngine
from geo.report import build_report


class GeoTests(unittest.TestCase):
    def setUp(self):
        network = patch('requests.sessions.Session.request', side_effect=AssertionError('禁止联网'))
        network.start()
        self.addCleanup(network.stop)
        env = patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'fixture-only', 'ARK_API_KEY': 'fixture-only',
                                      'DOUBAO_ENDPOINT_ID': 'ep-fixture'}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        sleep = patch('time.sleep')
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)
        self.payload = json.loads((Path(__file__).parent / 'fixtures/geo_response.json').read_text())
        self.brand = cli.read_yaml(cli.HERE / 'brand.yaml')
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        store_geo.migrate(self.db)
        self.args = SimpleNamespace(config=cli.HERE/'config.yaml', questions=cli.HERE/'questions.yaml',
                                    brand=cli.HERE/'brand.yaml', engines='deepseek', groups='brand',
                                    repeat=1, dry_run=False, db=':memory:')

    def response(self, status=200, payload=None):
        return Mock(status_code=status, json=Mock(return_value=self.payload if payload is None else payload))

    def sample(self):
        with patch('requests.post', return_value=self.response()):
            return DeepSeekEngine().ask('问题')

    def test_normal_response_and_storage(self):
        sample = self.sample()
        self.assertIsNone(sample['error'])
        self.assertEqual((sample['tokens_in'], sample['tokens_out']), (25, 45))
        self.assertEqual(sample['raw_json'], self.payload)
        result = analyze(sample['answer_text'], self.brand)
        self.assertTrue(result['mentioned'])
        self.assertEqual(result['company_rank'], 2)
        run = store_geo.start_run(self.db, 'v1', '')
        store_geo.save_sample(self.db, run, {'id':'q', 'group':'brand'}, 1, sample, result)
        saved = self.db.execute('SELECT raw_json, analysis_json FROM geo_samples').fetchone()
        self.assertEqual(json.loads(saved[0]), self.payload)
        self.assertEqual(json.loads(saved[1])['company_rank'], 2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM geo_attempts').fetchone()[0], 1)

    def test_alias_overlap_numeric_and_competitors(self):
        brand = dict(self.brand, competitors=[{'name':'甲公司', 'aliases':['甲企']}])
        result = analyze('甲企、*ST银亿、银亿股份、000981；10009810', brand)
        self.assertEqual(result['mention_count'], 3)
        self.assertEqual(result['first_pos'], 3)
        self.assertIsNone(result['company_rank'])
        self.assertEqual(result['competitors']['甲公司']['count'], 1)
        self.assertFalse(analyze('没有目标品牌', brand)['mentioned'])

    def test_domains_and_sentiment(self):
        result = analyze(self.payload['choices'][0]['message']['content'], self.brand)
        self.assertEqual(result['domains'], {'example.com':2, 'news.example.org':1})
        self.assertEqual(analyze('山子高科 看好', self.brand)['label'], '正面')
        self.assertEqual(analyze('山子高科 暴跌', self.brand)['label'], '负面')

    def test_429_retry_success(self):
        with patch('requests.post', side_effect=[self.response(429), self.response()]) as post:
            result = DeepSeekEngine().ask('问题')
        self.assertEqual(post.call_count, 2)
        self.assertIsNone(result['error'])
        self.assertEqual(result['attempts'][0]['error'], 'HTTP 429')
        self.sleep.assert_called_once_with(1)

    def test_5xx_retry_limit(self):
        with patch('requests.post', return_value=self.response(503)) as post:
            result = DeepSeekEngine().ask('问题')
        self.assertEqual(post.call_count, 4)
        self.assertEqual(result['error'], 'HTTP 503')
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [1,2,4])

    def test_4xx_no_retry_and_continue(self):
        with patch('requests.post', return_value=self.response(401)) as post:
            run = cli.run_sampling(self.args, self.db, log=lambda s: None)
        self.assertEqual(post.call_count, 10)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM geo_samples WHERE error IS NOT NULL').fetchone()[0], 10)
        self.assertTrue(store.is_blocked(self.db, 'geo:deepseek'))
        self.assertIsNotNone(self.db.execute('SELECT finished_at FROM geo_runs WHERE id=?', (run,)).fetchone()[0])

    def test_missing_key_skips(self):
        self.args.engines = 'deepseek,doubao'
        logs = []
        with patch.dict(os.environ, {}, clear=True), patch('requests.post') as post, patch('geo.cli.sqlite3.connect') as connect:
            self.assertIsNone(cli.run_sampling(self.args, log=logs.append))
        post.assert_not_called()
        connect.assert_not_called()
        self.assertEqual(sum('跳过' in s for s in logs), 2)

    def test_dry_run_no_network_or_database(self):
        self.args.dry_run = True
        self.args.engines = 'deepseek,doubao'
        self.args.groups = 'brand,category,holdout'
        self.args.repeat = 3
        logs = []
        with patch('requests.post') as post, patch('geo.cli.sqlite3.connect') as connect:
            cli.run_sampling(self.args, log=logs.append)
        post.assert_not_called()
        connect.assert_not_called()
        self.assertIn('调用数：180', logs[-1])
        self.assertIn('预估 token', logs[-1])

    def test_report_groups_errors_and_delta(self):
        sample = self.sample()
        for _ in range(2):
            run = store_geo.start_run(self.db, 'v1', '')
            for group in ('brand','category','holdout'):
                for idx, text in enumerate(('山子高科', '无提及', ''), 1):
                    row = dict(sample, answer_text=text, error='HTTP 400' if idx == 3 else None)
                    store_geo.save_sample(self.db, run, {'id':group, 'group':group}, idx,
                                          row, {} if row['error'] else analyze(text, self.brand))
            store_geo.finish_run(self.db, run)
        report = build_report(self.db, run)
        for group in ('brand','category','holdout'):
            self.assertIn('## '+group, report)
        self.assertEqual(report.count('| 2 | 1 | 1 | 50.0% |'), 3)
        self.assertEqual(report.count('+0.0 pp'), 3)
        self.assertIn('error 不计入分母', report)
        self.assertNotIn('总提及率', report)

    def test_backoff_skip_and_success_reset(self):
        store.record_failure(self.db, 'geo:deepseek', '失败')
        with patch('requests.post') as post:
            cli.run_sampling(self.args, self.db, log=lambda s: None)
        post.assert_not_called()
        store.record_success(self.db, 'geo:deepseek')
        with patch('requests.post', return_value=self.response()) as post:
            cli.run_sampling(self.args, self.db, log=lambda s: None)
        self.assertEqual(post.call_count, 10)
        self.assertFalse(store.is_blocked(self.db, 'geo:deepseek'))

    def test_web_search_extra_body(self):
        extra = {'fixture_search_option': {'enabled':True}}
        with patch('requests.post', return_value=self.response()) as post:
            engine = DoubaoEngine({'web_search':'on', 'extra_body':extra})
            engine.ask('问题')
        body = post.call_args.kwargs['json']
        self.assertEqual(body['fixture_search_option'], extra['fixture_search_option'])
        self.assertEqual(body['model'], 'ep-fixture')
        self.assertEqual(post.call_args.args[0], 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
        with patch('requests.post', return_value=self.response()) as post:
            DoubaoEngine({'extra_body':extra}).ask('问题')
        self.assertNotIn('fixture_search_option', post.call_args.kwargs['json'])
        with self.assertRaises(ValueError):
            DoubaoEngine({'web_search':'on'})

    def test_invalid_response_error(self):
        with patch('requests.post', return_value=self.response(payload={'choices':[]})) as post:
            result = DeepSeekEngine().ask('问题')
        self.assertIsNotNone(result['error'])
        post.assert_called_once()

    def test_monitor_geo_dispatch(self):
        with patch('sys.argv', ['monitor.py', 'geo', 'run', '--dry-run']), patch('geo.cli.main') as main:
            monitor.main()
        main.assert_called_once_with(['run', '--dry-run'])

    def test_cli_dry_run(self):
        output = io.StringIO()
        with patch('requests.post') as post, patch('geo.cli.sqlite3.connect') as connect, redirect_stdout(output):
            cli.main(['run','--dry-run'])
        post.assert_not_called()
        connect.assert_not_called()
        self.assertIn('调用数：180', output.getvalue())

    def test_error_only_denominator_and_version_change(self):
        sample = dict(self.sample(), error='HTTP 400')
        for version in ('v1', 'v2'):
            run = store_geo.start_run(self.db, version, '')
            store_geo.save_sample(self.db, run, {'id':'q','group':'brand'}, 1, sample, {})
        report = build_report(self.db)
        self.assertIn('| 0 | 1 | 0 | N/A | N/A | N/A | N/A |', report)


if __name__ == '__main__':
    unittest.main()
