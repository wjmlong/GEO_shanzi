from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
from urllib.parse import urlsplit
from typing import Any


LEGACY_INSIGHTS = [
    {"url": "https://www.sensteed.com/insights/article/keyinfo-304.html", "title": "历史关键信息归档 #304（官网专栏已静态化）", "date": "2026-11-23"},
    {"url": "https://www.sensteed.com/insights/article/keyinfo-303.html", "title": "历史关键信息归档 #303（官网专栏已静态化）", "date": "2026-11-23"},
    {"url": "https://www.sensteed.com/insights/article/keyinfo-302.html", "title": "历史关键信息归档 #302（官网专栏已静态化）", "date": "2026-11-18"},
    {"url": "https://www.sensteed.com/insights/article/keyinfo-301.html", "title": "历史关键信息归档 #301（官网专栏已静态化）", "date": "2026-11-17"},
    {"url": "https://www.sensteed.com/insights/article/keyinfo-300.html", "title": "历史关键信息归档 #300（官网专栏已静态化）", "date": "2026-11-16"},
    {"url": "https://www.sensteed.com/insights/article/keyinfo-299.html", "title": "历史关键信息归档 #299（官网专栏已静态化）", "date": "2026-11-11"},
]


def app_root_dir() -> pathlib.Path:
    """Resolve portable application root directory (works both in dev and PyInstaller exe)."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent


def bundle_resource_dir() -> pathlib.Path:
    """Resolve bundled static resources directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return pathlib.Path(getattr(sys, "_MEIPASS")) / "desktop_app"
    return pathlib.Path(__file__).resolve().parent


def data_dir() -> pathlib.Path:
    override = os.environ.get("SHANZIGEO_DATA_DIR", "").strip()
    p = pathlib.Path(override) if override else (app_root_dir() / "data")
    p.mkdir(parents=True, exist_ok=True)
    return p


def settings_path() -> pathlib.Path:
    return data_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    defaults = {
        "llm_api_url": "https://api.hai.network/compatible-preview/openai/v1",
        "llm_model_id": "deepseek-v4.1-flash",
        "llm_api_key": "",
        "official_endpoint_url": "https://www.sensteed.com/insights",
        "official_key_id": "",
        "official_secret": "",
        "cdp_port": 9233,
    }
    sp = settings_path()
    if sp.exists():
        try:
            loaded = json.loads(sp.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                defaults.update(loaded)
        except Exception:
            pass
    return defaults


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    cur = load_settings()
    for k in (
        "llm_api_url",
        "llm_model_id",
        "llm_api_key",
        "official_endpoint_url",
        "official_key_id",
        "official_secret",
        "cdp_port",
    ):
        if k in updates and updates[k] is not None:
            val = updates[k]
            # Preserve existing secret if masked placeholder submitted
            if k in ("llm_api_key", "official_secret") and str(val).strip() in ("", "***"):
                continue
            cur[k] = val
    settings_path().write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def platform_meta(acc: dict[str, Any]) -> dict[str, Any]:
    name = str(acc.get("account_name") or "")
    plat = str(acc.get("platform") or "custom").lower()
    url = str(acc.get("profile_url") or "")

    if plat == "manual":
        return {
            "code": f"CH-{int(acc['id']):02d}",
            "short_name": name,
            "hub_key": "",
            "ai_target": "手动发布",
            "summary": str(acc.get("notes") or ""),
            "badge": "sz-tag-slate",
            "editor_url": url,
            "domain": urlsplit(url).hostname or "",
            "is_official": False,
        }

    if "官网" in name or "sensteed.com" in url:
        return {
            "code": "CH-01",
            "short_name": "官网 · 关键信息",
            "hub_key": "official",
            "ai_target": "全引擎权威源",
            "summary": "1 秒自动静态化至 sensteed.com/insights/ 并刷新 Sitemap",
            "badge": "sz-tag-blue",
            "editor_url": "https://www.sensteed.com/insights/",
            "domain": "sensteed.com",
            "is_official": True,
        }
    if plat == "toutiao":
        return {
            "code": "CH-02",
            "short_name": "今日头条",
            "hub_key": "toutiao",
            "ai_target": "豆包核心源",
            "summary": "内置浏览器 0 Token 自动填标题与正文并发布/存草稿",
            "badge": "sz-tag-blue",
            "editor_url": "https://mp.toutiao.com/profile_v4/graphic/publish",
            "domain": "toutiao.com",
            "is_official": False,
        }
    if plat == "sohu":
        return {
            "code": "CH-03",
            "short_name": "搜狐号",
            "hub_key": "sohu",
            "ai_target": "DeepSeek 门户",
            "summary": "发布业务与财报拆解长文并回填线上链接",
            "badge": "sz-tag-slate",
            "editor_url": "https://mp.sohu.com/suc-ce/article/publish",
            "domain": "sohu.com",
            "is_official": False,
        }
    if plat == "netease":
        return {
            "code": "CH-04",
            "short_name": "网易号",
            "hub_key": "netease",
            "ai_target": "DeepSeek 补位",
            "summary": "覆盖产业协同与汽配业务增量门户收录",
            "badge": "sz-tag-slate",
            "editor_url": "https://mp.163.com/subscribe_v4/index.html#/article-publish",
            "domain": "163.com",
            "is_official": False,
        }
    if "东方财富" in name:
        return {
            "code": "CH-05",
            "short_name": "东方财富股吧",
            "hub_key": "eastmoney",
            "ai_target": "财经头号源",
            "summary": "发表带完整标题的独立主帖或财富号文章",
            "badge": "sz-tag-blue",
            "editor_url": "https://mp.eastmoney.com/collect/pc_article/index.html#/",
            "domain": "eastmoney.com",
            "is_official": False,
        }
    if "同花顺" in name:
        return {
            "code": "CH-06",
            "short_name": "同花顺社区",
            "hub_key": "ths",
            "ai_target": "财经高覆盖源",
            "summary": "同步标准问答与澄清主帖，避免仅回帖",
            "badge": "sz-tag-slate",
            "editor_url": "https://basic.10jqka.com.cn/000981/",
            "domain": "10jqka.com.cn",
            "is_official": False,
        }
    if plat == "douyin":
        return {
            "code": "CH-07",
            "short_name": "抖音",
            "hub_key": "douyin",
            "ai_target": "豆包视频简介",
            "summary": "发视频时完整填写 200 字网页摘要文字",
            "badge": "sz-tag-slate",
            "editor_url": "https://creator.douyin.com/creator-micro/content/upload",
            "domain": "douyin.com",
            "is_official": False,
        }
    if plat == "wechat":
        return {
            "code": "CH-08",
            "short_name": "微信公众号",
            "hub_key": "wechat",
            "ai_target": "元宝与官方母稿",
            "summary": "沉淀权威图文母稿，覆盖微信与腾讯元宝",
            "badge": "sz-tag-slate",
            "editor_url": "https://mp.weixin.qq.com/",
            "domain": "mp.weixin.qq.com",
            "is_official": False,
        }
    if plat == "xiaohongshu":
        return {
            "code": "CH-09",
            "short_name": "小红书",
            "hub_key": "xiaohongshu",
            "ai_target": "图文日常触达",
            "summary": "复用图文卡片触达个人投资者日常检索",
            "badge": "sz-tag-slate",
            "editor_url": "https://creator.xiaohongshu.com/publish/publish",
            "domain": "xiaohongshu.com",
            "is_official": False,
        }
    return {
        "code": "CH-00",
        "short_name": name or "扩展渠道",
        "hub_key": plat,
        "ai_target": "综合渠道",
        "summary": "外部传播渠道",
        "badge": "sz-tag-slate",
        "editor_url": url or "#",
        "domain": "",
        "is_official": False,
    }


class GeoLocalDB:
    def __init__(self, db_path: pathlib.Path | None = None) -> None:
        self.db_path = db_path or (data_dir() / "shanzi_geo.db")
        self._init_schema()
        self._seed_if_empty()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT DEFAULT '',
                    content TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS title_libraries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS titles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    title TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS keyword_libraries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    library_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    profile_url TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    excerpt TEXT DEFAULT '',
                    keywords TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    score INTEGER DEFAULT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    row_type TEXT NOT NULL,
                    article_id INTEGER DEFAULT NULL,
                    account_id INTEGER DEFAULT NULL,
                    platform_label TEXT NOT NULL,
                    ai_target TEXT DEFAULT '',
                    badge TEXT DEFAULT 'sz-tag-slate',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ready',
                    url TEXT DEFAULT '',
                    editor_url TEXT DEFAULT '#',
                    citations INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS citation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    engine TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    our_citation_rate REAL DEFAULT 0,
                    unprompted_rate REAL DEFAULT 0,
                    sensitive_accuracy REAL DEFAULT 0,
                    cited_urls_json TEXT DEFAULT '[]',
                    details_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def _seed_if_empty(self) -> None:
        with self.connect() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
            if cnt > 0:
                return
            seed_file = bundle_resource_dir() / "seed_data.json"
            if not seed_file.exists():
                return
            seed = json.loads(seed_file.read_text(encoding="utf-8"))
            now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

            for kb in seed.get("knowledge_bases", []):
                conn.execute(
                    "INSERT INTO knowledge_bases (id, name, description, content, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (kb["id"], kb["name"], kb.get("description") or "", kb["content"], now[:10]),
                )
            for pr in seed.get("prompts", []):
                conn.execute(
                    "INSERT INTO prompts (id, name, type, content) VALUES (?, ?, ?, ?)",
                    (pr["id"], pr["name"], pr.get("type") or "", pr["content"]),
                )
            for tl in seed.get("title_libraries", []):
                conn.execute(
                    "INSERT INTO title_libraries (id, name, description) VALUES (?, ?, ?)",
                    (tl["id"], tl["name"], tl.get("description") or ""),
                )
            for ti in seed.get("titles", []):
                conn.execute(
                    "INSERT INTO titles (id, library_id, title) VALUES (?, ?, ?)",
                    (ti["id"], ti["library_id"], ti["title"]),
                )
            for kl in seed.get("keyword_libraries", []):
                conn.execute(
                    "INSERT INTO keyword_libraries (id, name, description) VALUES (?, ?, ?)",
                    (kl["id"], kl["name"], kl.get("description") or ""),
                )
            for kw in seed.get("keywords", []):
                conn.execute(
                    "INSERT INTO keywords (id, library_id, keyword) VALUES (?, ?, ?)",
                    (kw["id"], kw["library_id"], kw["keyword"]),
                )

            acc_map: dict[int, dict[str, Any]] = {}
            official_acc_id = None
            for acc in seed.get("accounts", []):
                conn.execute(
                    "INSERT INTO accounts (id, account_name, platform, profile_url, notes, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                    (acc["id"], acc["account_name"], acc["platform"], acc.get("profile_url") or "", acc.get("notes") or ""),
                )
                meta = platform_meta(acc)
                acc_map[int(acc["id"])] = {**acc, **meta}
                if meta["is_official"]:
                    official_acc_id = int(acc["id"])

            art_map: dict[int, dict[str, Any]] = {}
            for a in seed.get("articles", []):
                conn.execute(
                    "INSERT INTO articles (id, title, slug, excerpt, keywords, content, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        a["id"],
                        a["title"],
                        a["slug"],
                        a.get("excerpt") or "",
                        a.get("keywords") or "",
                        a["content"],
                        str(a.get("updated_at") or now)[:16],
                    ),
                )
                art_map[int(a["id"])] = a

            # Seed official synced articles
            for od in reversed(seed.get("official_distributions", [])):
                a = art_map.get(int(od["article_id"]), {})
                conn.execute(
                    """INSERT INTO ledger (row_type, article_id, account_id, platform_label, ai_target, badge, title, content, status, url, editor_url, citations, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, 'https://www.sensteed.com/insights/', 0, ?)""",
                    (
                        "official",
                        od["article_id"],
                        official_acc_id,
                        "官网 · 关键信息",
                        "全引擎权威源",
                        "sz-tag-blue",
                        a.get("title") or "官网已发布文章",
                        a.get("content") or "",
                        od["remote_url"],
                        str(od.get("updated_at") or now)[:16],
                    ),
                )
            for leg in LEGACY_INSIGHTS:
                conn.execute(
                    """INSERT INTO ledger (row_type, article_id, account_id, platform_label, ai_target, badge, title, content, status, url, editor_url, citations, updated_at)
                       VALUES ('official_archive', NULL, ?, '官网 · 关键信息', '全引擎权威源', 'sz-tag-blue', ?, '', 'completed', ?, 'https://www.sensteed.com/insights/', 0, ?)""",
                    (official_acc_id, leg["title"], leg["url"], leg["date"]),
                )
            for mp in reversed(seed.get("manual_publications", [])):
                aid = int(mp["account_id"]) if mp.get("account_id") else None
                am = acc_map.get(aid or -1, {})
                art = art_map.get(int(mp["article_id"]) if mp.get("article_id") else -1, {})
                title = art.get("title") or str(mp.get("content") or "").splitlines()[0].lstrip("# ").strip() or "未命名稿件"
                body = art.get("content") or str(mp.get("content") or "")
                conn.execute(
                    """INSERT INTO ledger (row_type, article_id, account_id, platform_label, ai_target, badge, title, content, status, url, editor_url, citations, updated_at)
                       VALUES ('manual', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (
                        mp.get("article_id"),
                        aid,
                        am.get("short_name") or mp.get("platform") or "外部平台",
                        am.get("ai_target") or "外部渠道",
                        am.get("badge") or "sz-tag-slate",
                        title,
                        body,
                        mp.get("status") or "ready",
                        mp.get("completion_url") or "",
                        am.get("editor_url") or "#",
                        str(mp.get("completed_at") or mp.get("updated_at") or now)[:16],
                    ),
                )

    def dashboard_state(self) -> dict[str, Any]:
        with self.connect() as conn:
            accounts = [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE is_active=1 ORDER BY account_name").fetchall()]
            ledger = [dict(r) for r in conn.execute("SELECT * FROM ledger ORDER BY CASE WHEN status='completed' THEN 1 ELSE 0 END ASC, id DESC").fetchall()]
            articles = [dict(r) for r in conn.execute("SELECT id, title, slug, score, updated_at FROM articles ORDER BY id DESC LIMIT 50").fetchall()]
            title_libs = [dict(r) for r in conn.execute("SELECT * FROM title_libraries ORDER BY id").fetchall()]
            titles = [dict(r) for r in conn.execute("SELECT * FROM titles ORDER BY id DESC").fetchall()]
            kw_libs = [dict(r) for r in conn.execute("SELECT * FROM keyword_libraries ORDER BY id").fetchall()]
            kws = [dict(r) for r in conn.execute("SELECT * FROM keywords ORDER BY id DESC").fetchall()]
            kbs = [dict(r) for r in conn.execute("SELECT * FROM knowledge_bases ORDER BY id").fetchall()]
            runs = [dict(r) for r in conn.execute("SELECT * FROM citation_runs ORDER BY id DESC LIMIT 12").fetchall()]

        platforms = []
        by_acc: dict[int, dict[str, Any]] = {}
        for acc in accounts:
            meta = platform_meta(acc)
            item = {
                "id": acc["id"],
                "name": acc["account_name"],
                "platform": acc["platform"],
                **meta,
                "published_count": 0,
                "pending_count": 0,
                "citation_count": 0,
            }
            platforms.append(item)
            by_acc[acc["id"]] = item

        for row in ledger:
            aid = row.get("account_id")
            if aid in by_acc:
                if row["status"] == "completed":
                    by_acc[aid]["published_count"] += 1
                else:
                    by_acc[aid]["pending_count"] += 1
                by_acc[aid]["citation_count"] += int(row.get("citations") or 0)

        platforms.sort(key=lambda x: (x["platform"] == "manual", x["id"] if x["platform"] == "manual" else x["code"]))
        pub_cnt = sum(1 for r in ledger if r["status"] == "completed")
        cited_urls = sum(1 for r in ledger if int(r.get("citations") or 0) > 0)
        cite_hits = sum(int(r.get("citations") or 0) for r in ledger)

        return {
            "summary": {
                "total_rows": len(ledger),
                "published_count": pub_cnt,
                "pending_count": len(ledger) - pub_cnt,
                "cited_urls": cited_urls,
                "citation_hits": cite_hits,
                "citation_rate": round(100.0 * cited_urls / pub_cnt, 1) if pub_cnt else 0.0,
            },
            "platforms": platforms,
            "ledger": ledger,
            "articles": articles,
            "title_libraries": title_libs,
            "titles": titles,
            "keyword_libraries": kw_libs,
            "keywords": kws,
            "knowledge_bases": kbs,
            "citation_runs": runs,
        }
