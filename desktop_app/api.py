from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import sys
import urllib.parse
from typing import Any

import yaml
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from desktop_app.db import (
    GeoLocalDB,
    app_root_dir,
    bundle_resource_dir,
    data_dir,
    load_settings,
    platform_meta,
    save_settings,
)
from desktop_app.services import (
    PLATFORM_URLS,
    AiComplianceAndWriterService,
    OfficialSitePublisher,
    PortableBrowserEngine,
    find_portable_chromium,
)

FALLBACK_EXAM_SPEC: dict[str, Any] = {
    "version": 1,
    "name": "山子高科(000981.SZ) GEO 零成本真机联网 10 题核心基线考卷",
    "description": "用于每周固定评测网页版豆包与 DeepSeek（开启联网）的三大核心指标：我方信源被翻牌率、行业无提示主动提名率、敏感问题口径答对率。",
    "brand_terms": ["山子高科", "山子高科技", "000981", "邦奇动力", "艾尔希"],
    "own_domains": [
        "sensteed.com",
        "toutiao.com",
        "sohu.com",
        "163.com",
        "eastmoney.com",
        "10jqka.com.cn",
        "iesdouyin.com",
        "douyin.com",
    ],
    "competitors": ["万里扬", "均胜电子", "精进电动", "华海诚科", "德邦科技"],
    "questions": [
        {
            "id": "Q01",
            "group": "industry_unprompted",
            "topic_id": 2,
            "keyword": "国内新能源汽车混动变速箱DHT与CVT上市公司",
            "text": "国内做新能源汽车混动变速箱（DHT）和自动变速器（CVT）的A股上市公司有哪些？",
        },
        {
            "id": "Q02",
            "group": "industry_unprompted",
            "topic_id": 2,
            "keyword": "国内汽车安全气囊气体发生器供应商上市公司",
            "text": "国内汽车安全气囊气体发生器核心供应商和相关上市公司有哪些？",
        },
        {
            "id": "Q03",
            "group": "industry_unprompted",
            "topic_id": 3,
            "keyword": "布局汽车零部件与半导体先进封装材料上市公司",
            "text": "国内同时布局汽车核心零部件和半导体先进封装材料的A股上市公司有哪些？",
        },
        {
            "id": "Q04",
            "group": "industry_unprompted",
            "topic_id": 2,
            "keyword": "邦奇动力DHT120与双逆变器技术特点及所属上市公司",
            "text": "邦奇动力（Punch Powertrain）的DHT120混动电驱和双逆变器技术特点是什么？属于哪家上市公司？",
        },
        {
            "id": "Q05",
            "group": "industry_unprompted",
            "topic_id": 2,
            "keyword": "艾尔希ARC安全气囊气体发生器行业地位及关联上市公司",
            "text": "艾尔希（ARC）安全气囊气体发生器的全球行业地位如何？和哪家A股公司有关？",
        },
        {
            "id": "Q06",
            "group": "sensitive_clarification",
            "topic_id": 1,
            "keyword": "山子高科参与哪吒汽车破产重整澄清公告",
            "text": "山子高科参与哪吒汽车破产重整投资是真的吗？官方有没有澄清公告？",
            "must_include_any": ["未直接或间接参与", "2026-040", "无股权控制关系", "澄清"],
            "must_avoid_any": ["已确认收购哪吒", "上市公司直接注资哪吒"],
        },
        {
            "id": "Q07",
            "group": "sensitive_clarification",
            "topic_id": 1,
            "keyword": "山子高科是否ST及与银亿股份关系",
            "text": "山子高科现在还是ST股票吗？和以前的银亿股份是什么关系？",
            "must_include_any": ["非ST", "不是ST", "摘帽", "更名", "重整"],
            "must_avoid_any": ["目前仍为ST", "当前属于ST股票"],
        },
        {
            "id": "Q08",
            "group": "sensitive_clarification",
            "topic_id": 1,
            "keyword": "山子高科2026年三季报业绩与亏损原因",
            "text": "山子高科2026年三季报业绩怎么样？为什么单季营收增长但净利润仍为负？",
            "must_include_any": ["20.90", "7.19", "4.93%", "扣非"],
        },
        {
            "id": "Q09",
            "group": "brand_core",
            "topic_id": 1,
            "keyword": "山子高科主营业务与核心子公司海外营收",
            "text": "山子高科（000981）的主营业务和核心子公司有哪些？海外营收占比多少？",
            "must_include_any": ["邦奇", "艾尔希", "53.42%"],
        },
        {
            "id": "Q10",
            "group": "brand_core",
            "topic_id": 4,
            "keyword": "山子高科芯片半导体与整车出海产业链协同布局",
            "text": "山子高科在芯片半导体和整车出海方面有哪些最新布局？",
            "must_include_any": ["先进封装材料", "半导体"],
        },
    ],
}


def load_exam_spec() -> dict[str, Any]:
    """Load baseline 10-question exam + 5 competitors from geo/baseline_10q.yaml or bundled fallback."""
    candidates: list[pathlib.Path] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = pathlib.Path(getattr(sys, "_MEIPASS"))
        candidates.append(meipass / "geo" / "baseline_10q.yaml")
        candidates.append(meipass / "desktop_app" / "baseline_10q.yaml")
    res_dir = bundle_resource_dir()
    candidates.extend(
        [
            res_dir.parent / "geo" / "baseline_10q.yaml",
            app_root_dir() / "geo" / "baseline_10q.yaml",
            res_dir / "baseline_10q.yaml",
        ]
    )
    for path in candidates:
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("questions"), list):
                    return {
                        "version": loaded.get("version", 1),
                        "name": loaded.get("name") or FALLBACK_EXAM_SPEC["name"],
                        "description": loaded.get("description") or FALLBACK_EXAM_SPEC["description"],
                        "brand_terms": list(loaded.get("brand_terms") or FALLBACK_EXAM_SPEC["brand_terms"]),
                        "own_domains": list(loaded.get("own_domains") or FALLBACK_EXAM_SPEC["own_domains"]),
                        "competitors": list(loaded.get("competitors") or FALLBACK_EXAM_SPEC["competitors"]),
                        "questions": list(loaded["questions"]),
                    }
            except Exception:
                continue
    return json.loads(json.dumps(FALLBACK_EXAM_SPEC, ensure_ascii=False))


def _mask_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "llm_api_url": str(settings.get("llm_api_url") or ""),
        "llm_model_id": str(settings.get("llm_model_id") or "deepseek-v4.1-flash"),
        "has_llm_key": bool(str(settings.get("llm_api_key") or "").strip()),
        "official_endpoint_url": str(settings.get("official_endpoint_url") or ""),
        "official_key_id": str(settings.get("official_key_id") or ""),
        "has_official_secret": bool(str(settings.get("official_secret") or "").strip()),
        "cdp_port": int(settings.get("cdp_port") or 9233),
    }


def _norm_url(raw_url: str) -> str:
    s = (raw_url or "").strip()
    if not s:
        return ""
    try:
        parsed = urllib.parse.urlsplit(s)
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path.rstrip("/")
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{scheme}://{netloc}{path}{query}" if netloc else s.rstrip("/")
    except Exception:
        return s.rstrip("/")


class GenerateArticleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_title: str = ""
    title: str = ""
    topic: str = ""
    style: str = "long"


class InspectArticleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    content: str
    article_id: int | None = None


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = "upload"
    article_id: int | None = None
    ledger_id: int | None = None
    title: str | None = None
    content: str | None = None
    keywords: str | None = None
    score: int | None = None
    account_ids: list[int] = Field(default_factory=list)
    external_action: str = "draft"


class BrowserOpenRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    platform: str | None = None
    url: str | None = None
    account_id: int | None = None


class LedgerReceiptRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ledger_id: int
    url: str


class AssetTitleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    library_id: int = 1
    title: str


class AssetKeywordRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    library_id: int = 1
    keyword: str


class AssetKbUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    content: str


class BaselineRecordRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    engine: str
    our_citation_rate: float = 0.0
    unprompted_rate: float = 0.0
    sensitive_accuracy: float = 0.0
    cited_urls: list[str] | str | None = None
    notes: str | None = ""
    run_date: str | None = None


def create_app(db_path: pathlib.Path | str | None = None) -> FastAPI:
    resolved_db_path = pathlib.Path(db_path) if db_path is not None else None
    db = GeoLocalDB(db_path=resolved_db_path)
    init_cfg = load_settings()
    browser_engine = PortableBrowserEngine(cdp_port=int(init_cfg.get("cdp_port") or 9233))

    app = FastAPI(title="山子高科 GEO 智能工作台 API", version="1.0.0")
    app.state.db = db
    app.state.browser_engine = browser_engine

    @app.exception_handler(HTTPException)
    async def _http_exc_handler(_req: Request, exc: HTTPException) -> JSONResponse:
        msg = str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": msg, "detail": msg, "message": msg})

    @app.exception_handler(RequestValidationError)
    async def _validation_exc_handler(_req: Request, exc: RequestValidationError) -> JSONResponse:
        msg = f"请求参数格式有误: {exc.errors()}"
        return JSONResponse(status_code=422, content={"ok": False, "error": msg, "detail": exc.errors(), "message": msg})

    @app.exception_handler(Exception)
    async def _unhandled_exc_handler(_req: Request, exc: Exception) -> JSONResponse:
        msg = str(exc) or exc.__class__.__name__
        return JSONResponse(status_code=400, content={"ok": False, "error": msg, "detail": msg, "message": msg})

    @app.get("/", response_class=HTMLResponse)
    async def serve_index() -> HTMLResponse:
        index_path = bundle_resource_dir() / "static" / "index.html"
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        return HTMLResponse(
            "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<title>山子高科 GEO 智能工作台</title></head>"
            "<body><div id='app'>山子高科 GEO 智能工作台 API 已就绪</div></body></html>"
        )

    @app.get("/api/health")
    async def api_health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/api/state")
    async def api_state() -> dict[str, Any]:
        dash = await run_in_threadpool(db.dashboard_state)
        # Enrich articles with content/excerpt/keywords so selecting saved articles in UI populates editor cleanly
        with db.connect() as conn:
            art_extra = {
                int(r["id"]): dict(r)
                for r in conn.execute("SELECT id, content, excerpt, keywords FROM articles").fetchall()
            }
        for art in dash.get("articles", []):
            ext = art_extra.get(int(art["id"]))
            if ext:
                art.setdefault("content", ext.get("content") or "")
                art.setdefault("excerpt", ext.get("excerpt") or "")
                art.setdefault("keywords", ext.get("keywords") or "")

        # Enrich citation_runs with parsed cited_urls and notes alongside raw JSON strings
        for run in dash.get("citation_runs", []):
            try:
                parsed_urls = json.loads(run.get("cited_urls_json") or "[]")
                run["cited_urls"] = parsed_urls if isinstance(parsed_urls, list) else []
            except Exception:
                run["cited_urls"] = []
            try:
                parsed_details = json.loads(run.get("details_json") or "{}")
                run["notes"] = str(parsed_details.get("notes") or "") if isinstance(parsed_details, dict) else ""
            except Exception:
                run["notes"] = ""

        settings = load_settings()
        browser_engine.cdp_port = int(settings.get("cdp_port") or 9233)
        is_browser_up = await run_in_threadpool(browser_engine.is_running)
        chrome_path = await run_in_threadpool(find_portable_chromium)
        exam_spec = load_exam_spec()

        return {
            "ok": True,
            **dash,
            "browser_running": is_browser_up,
            "chromium_path": str(chrome_path or ""),
            "data_dir": str(data_dir()),
            "settings_masked": _mask_settings(settings),
            "exam_questions": exam_spec["questions"],
            "competitors": exam_spec["competitors"],
            "exam_spec": exam_spec,
        }

    @app.get("/api/articles/{article_id}")
    async def api_get_article(article_id: int) -> dict[str, Any]:
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="稿件不存在")
        return {"ok": True, "article": dict(row)}

    @app.post("/api/ai/generate")
    async def api_ai_generate(payload: GenerateArticleRequest) -> dict[str, Any]:
        topic = (payload.topic_title or payload.title or payload.topic).strip()
        if not topic:
            raise HTTPException(status_code=400, detail="请先选择或输入文章题目")
        style = payload.style if payload.style in ("long", "qa", "douyin") else "long"
        svc = AiComplianceAndWriterService(db, load_settings())
        res = await run_in_threadpool(svc.generate_article, topic, style)
        return {"ok": True, "title": res["title"], "content": res["content"]}

    @app.post("/api/ai/inspect")
    async def api_ai_inspect(payload: InspectArticleRequest) -> dict[str, Any]:
        title = payload.title.strip()
        content = payload.content.strip()
        if not title or not content:
            raise HTTPException(status_code=400, detail="请填写文章标题与正文后再开始合规质检")
        svc = AiComplianceAndWriterService(db, load_settings())
        res = await run_in_threadpool(svc.inspect_article, title, content)
        if payload.article_id:
            with db.connect() as conn:
                conn.execute("UPDATE articles SET score=? WHERE id=?", (int(res["score"]), payload.article_id))
        return {
            "ok": True,
            "score": res["score"],
            "passed": res["passed"],
            "summary": res["summary"],
            "dimensions": res["dimensions"],
            "issues": res["issues"],
        }

    @app.post("/api/dispatch")
    async def api_dispatch(payload: DispatchRequest) -> dict[str, Any]:
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        settings = load_settings()
        browser_engine.cdp_port = int(settings.get("cdp_port") or 9233)

        ledger_seed_row: dict[str, Any] | None = None
        if payload.ledger_id:
            with db.connect() as conn:
                lr = conn.execute("SELECT * FROM ledger WHERE id=?", (payload.ledger_id,)).fetchone()
                if lr:
                    ledger_seed_row = dict(lr)

        article: dict[str, Any] | None = None
        if payload.mode == "existing":
            target_art_id = payload.article_id or (ledger_seed_row.get("article_id") if ledger_seed_row else None)
            if target_art_id:
                with db.connect() as conn:
                    row = conn.execute("SELECT * FROM articles WHERE id=?", (int(target_art_id),)).fetchone()
                    if row:
                        article = dict(row)
                        if payload.title and payload.content:
                            article["title"] = payload.title.strip()
                            article["content"] = payload.content.strip()
                            conn.execute(
                                "UPDATE articles SET title=?, content=?, updated_at=? WHERE id=?",
                                (article["title"], article["content"], now, article["id"]),
                            )
            if article is None and ledger_seed_row:
                article = {
                    "id": ledger_seed_row.get("article_id"),
                    "title": (payload.title or ledger_seed_row.get("title") or "").strip(),
                    "slug": f"ledger-{ledger_seed_row['id']}",
                    "excerpt": "",
                    "keywords": payload.keywords or "",
                    "content": (payload.content or ledger_seed_row.get("content") or "").strip(),
                    "score": payload.score,
                    "updated_at": now,
                }

        if article is None:
            title = (payload.title or "").strip()
            content = (payload.content or "").strip()
            if not title or not content:
                raise HTTPException(status_code=400, detail="标题与正文不能为空")
            digest = hashlib.md5(f"{title}-{now}".encode("utf-8")).hexdigest()[:8]
            slug = f"post-{digest}"
            plain = re.sub(r"[#*`>\-\r\n]+", " ", content).strip()
            excerpt = plain[:140]
            keywords = (payload.keywords or "山子高科,000981,邦奇动力,艾尔希ARC,半导体先进封装材料").strip()
            with db.connect() as conn:
                cur = conn.execute(
                    """INSERT INTO articles (title, slug, excerpt, keywords, content, score, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (title, slug, excerpt, keywords, content, payload.score, now),
                )
                art_id = int(cur.lastrowid)
            article = {
                "id": art_id,
                "title": title,
                "slug": slug,
                "excerpt": excerpt,
                "keywords": keywords,
                "content": content,
                "score": payload.score,
                "updated_at": now,
            }

        account_ids = list(payload.account_ids)
        if not account_ids and ledger_seed_row and ledger_seed_row.get("account_id"):
            account_ids = [int(ledger_seed_row["account_id"])]
        if not account_ids:
            raise HTTPException(status_code=400, detail="请至少选择一个发布阵地")

        with db.connect() as conn:
            placeholders = ",".join("?" for _ in account_ids)
            acc_rows = conn.execute(f"SELECT * FROM accounts WHERE id IN ({placeholders})", account_ids).fetchall()
        acc_by_id = {int(r["id"]): dict(r) for r in acc_rows}
        ordered_accounts = [acc_by_id[aid] for aid in account_ids if aid in acc_by_id]
        if not ordered_accounts:
            raise HTTPException(status_code=404, detail="所选发布阵地不存在")

        external_action = payload.external_action if payload.external_action in ("draft", "publish", "ledger_only") else "draft"
        msgs: list[str] = []
        results: list[dict[str, Any]] = []

        for acc in ordered_accounts:
            acc_id = int(acc["id"])
            meta = platform_meta(acc)
            short_name = meta["short_name"]

            if meta["is_official"]:
                try:
                    pub = await run_in_threadpool(OfficialSitePublisher(settings).publish_article, article)
                    remote_url = str(pub.get("remote_url") or "")
                    with db.connect() as conn:
                        existing = (
                            conn.execute(
                                "SELECT id FROM ledger WHERE article_id=? AND account_id=? ORDER BY id DESC LIMIT 1",
                                (article["id"], acc_id),
                            ).fetchone()
                            if article.get("id")
                            else None
                        )
                        if existing:
                            ledger_id = int(existing["id"])
                            conn.execute(
                                "UPDATE ledger SET status='completed', url=?, title=?, content=?, updated_at=? WHERE id=?",
                                (remote_url, article["title"], article["content"], now, ledger_id),
                            )
                        else:
                            cur = conn.execute(
                                """INSERT INTO ledger
                                   (row_type, article_id, account_id, platform_label, ai_target, badge, title, content, status, url, editor_url, citations, updated_at)
                                   VALUES ('official', ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, 0, ?)""",
                                (
                                    article.get("id"),
                                    acc_id,
                                    short_name,
                                    meta["ai_target"],
                                    meta["badge"],
                                    article["title"],
                                    article["content"],
                                    remote_url,
                                    meta["editor_url"],
                                    now,
                                ),
                            )
                            ledger_id = int(cur.lastrowid)
                    msg = f"{short_name}直发成功（{remote_url}）"
                    msgs.append(msg)
                    results.append(
                        {
                            "account_id": acc_id,
                            "ledger_id": ledger_id,
                            "platform": short_name,
                            "code": meta["code"],
                            "ok": True,
                            "status": "completed",
                            "url": remote_url,
                            "message": msg,
                        }
                    )
                except Exception as exc:
                    msg = f"{short_name}直发失败：{exc}"
                    msgs.append(msg)
                    results.append(
                        {
                            "account_id": acc_id,
                            "platform": short_name,
                            "code": meta["code"],
                            "ok": False,
                            "status": "failed",
                            "url": "",
                            "message": msg,
                        }
                    )
                continue

            # Non-official external platform: ensure ledger row exists
            with db.connect() as conn:
                existing_row = None
                if payload.ledger_id and ledger_seed_row and ledger_seed_row.get("account_id") == acc_id:
                    existing_row = ledger_seed_row
                elif article.get("id") is not None:
                    r = conn.execute(
                        "SELECT * FROM ledger WHERE article_id=? AND account_id=? ORDER BY id DESC LIMIT 1",
                        (article["id"], acc_id),
                    ).fetchone()
                    if r:
                        existing_row = dict(r)

                if existing_row:
                    ledger_id = int(existing_row["id"])
                    conn.execute(
                        "UPDATE ledger SET title=?, content=?, updated_at=? WHERE id=?",
                        (article["title"], article["content"], now, ledger_id),
                    )
                    current_status = str(existing_row.get("status") or "ready")
                    current_url = str(existing_row.get("url") or "")
                else:
                    cur = conn.execute(
                        """INSERT INTO ledger
                           (row_type, article_id, account_id, platform_label, ai_target, badge, title, content, status, url, editor_url, citations, updated_at)
                           VALUES ('manual', ?, ?, ?, ?, ?, ?, ?, 'ready', '', ?, 0, ?)""",
                        (
                            article.get("id"),
                            acc_id,
                            short_name,
                            meta["ai_target"],
                            meta["badge"],
                            article["title"],
                            article["content"],
                            meta["editor_url"],
                            now,
                        ),
                    )
                    ledger_id = int(cur.lastrowid)
                    current_status = "ready"
                    current_url = ""

            if external_action == "ledger_only":
                msg = f"{short_name}已记入待发工单台账"
                msgs.append(msg)
                results.append(
                    {
                        "account_id": acc_id,
                        "ledger_id": ledger_id,
                        "platform": short_name,
                        "code": meta["code"],
                        "ok": True,
                        "status": current_status,
                        "url": current_url,
                        "message": msg,
                    }
                )
                continue

            pub_res = await browser_engine.publish_article(
                meta["hub_key"],
                article["title"],
                article["content"],
                external_action,
                meta["editor_url"],
            )
            live_url = str(pub_res.get("url") or "").strip()
            pub_status = str(pub_res.get("status") or "")
            raw_msg = str(pub_res.get("message") or pub_res.get("error") or "操作已执行")
            msg = raw_msg if short_name in raw_msg or meta["hub_key"] in raw_msg else f"{short_name}：{raw_msg}"

            if live_url:
                new_status = "completed"
                with db.connect() as conn:
                    conn.execute(
                        "UPDATE ledger SET status='completed', url=?, updated_at=? WHERE id=?",
                        (live_url, now, ledger_id),
                    )
            elif pub_res.get("ok") or pub_status in ("draft_saved", "submitted"):
                new_status = "in_progress"
                with db.connect() as conn:
                    conn.execute(
                        "UPDATE ledger SET status='in_progress', updated_at=? WHERE id=?",
                        (now, ledger_id),
                    )
            else:
                new_status = current_status

            msgs.append(msg)
            results.append(
                {
                    "account_id": acc_id,
                    "ledger_id": ledger_id,
                    "platform": short_name,
                    "code": meta["code"],
                    "ok": bool(pub_res.get("ok")),
                    "status": new_status,
                    "url": live_url or current_url,
                    "message": msg,
                }
            )

        return {
            "ok": True,
            "article_id": article.get("id"),
            "message": "；".join(msgs),
            "results": results,
        }

    @app.post("/api/browser/open")
    async def api_browser_open(payload: BrowserOpenRequest | None = Body(default=None)) -> dict[str, Any]:
        settings = load_settings()
        browser_engine.cdp_port = int(settings.get("cdp_port") or 9233)

        req = payload or BrowserOpenRequest()
        target_url = (req.url or "").strip()
        if target_url == "#":
            target_url = ""

        if not target_url and req.account_id:
            with db.connect() as conn:
                acc_row = conn.execute("SELECT * FROM accounts WHERE id=?", (req.account_id,)).fetchone()
            if acc_row:
                target_url = platform_meta(dict(acc_row)).get("editor_url") or ""

        if not target_url and req.platform:
            plat_key = req.platform.strip()
            plat_lower = plat_key.lower()
            if plat_lower == "official":
                target_url = "https://www.sensteed.com/insights/"
            elif plat_lower in PLATFORM_URLS:
                target_url = PLATFORM_URLS[plat_lower]
            else:
                with db.connect() as conn:
                    accs = [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE is_active=1").fetchall()]
                for acc in accs:
                    meta = platform_meta(acc)
                    if plat_key.upper() == meta["code"] or plat_lower == meta["hub_key"] or plat_key in meta["short_name"]:
                        target_url = meta["editor_url"]
                        break

        if target_url and target_url != "#":
            return await browser_engine.open_url(target_url)
        return await run_in_threadpool(browser_engine.ensure_started)

    @app.post("/api/ledger/receipt")
    async def api_ledger_receipt(payload: LedgerReceiptRequest) -> dict[str, Any]:
        clean_url = payload.url.strip()
        if not clean_url:
            raise HTTPException(status_code=400, detail="请填写有效的线上真实链接")
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        with db.connect() as conn:
            cur = conn.execute(
                "UPDATE ledger SET status='completed', url=?, updated_at=? WHERE id=?",
                (clean_url, now, payload.ledger_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="未找到对应的台账记录")
        return {"ok": True, "ledger_id": payload.ledger_id, "url": clean_url, "status": "completed", "updated_at": now}

    @app.get("/api/ledger/export.csv")
    async def api_ledger_export_csv() -> StreamingResponse:
        with db.connect() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM ledger ORDER BY CASE WHEN status='completed' THEN 1 ELSE 0 END ASC, id DESC"
                ).fetchall()
            ]
        status_labels = {
            "completed": "已上线",
            "in_progress": "草稿/审核中",
            "ready": "待发布",
        }
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["序号", "发布平台", "目标AI引擎", "文章标题", "发布状态", "线上真实链接", "AI被翻牌次数", "更新时间"])
        for idx, r in enumerate(rows, start=1):
            st_raw = str(r.get("status") or "ready")
            writer.writerow(
                [
                    idx,
                    r.get("platform_label") or "",
                    r.get("ai_target") or "",
                    r.get("title") or "",
                    status_labels.get(st_raw, st_raw),
                    r.get("url") or "",
                    int(r.get("citations") or 0),
                    r.get("updated_at") or "",
                ]
            )
        csv_bytes = buf.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            iter([csv_bytes]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="shanzi_geo_ledger.csv"'},
        )

    @app.post("/api/assets/title")
    async def api_add_title(payload: AssetTitleRequest) -> dict[str, Any]:
        items = [line.strip() for line in re.split(r"[\r\n]+", payload.title) if line.strip()]
        if not items:
            raise HTTPException(status_code=400, detail="标题内容不能为空")
        inserted_ids: list[int] = []
        with db.connect() as conn:
            lib_row = conn.execute("SELECT id FROM title_libraries WHERE id=?", (payload.library_id,)).fetchone()
            lib_id = int(lib_row["id"]) if lib_row else 1
            for t in items:
                cur = conn.execute("INSERT INTO titles (library_id, title) VALUES (?, ?)", (lib_id, t))
                inserted_ids.append(int(cur.lastrowid))
        return {"ok": True, "id": inserted_ids[0], "ids": inserted_ids, "added": len(inserted_ids)}

    @app.delete("/api/assets/title/{item_id}")
    async def api_delete_title(item_id: int) -> dict[str, Any]:
        with db.connect() as conn:
            cur = conn.execute("DELETE FROM titles WHERE id=?", (item_id,))
        return {"ok": True, "deleted": cur.rowcount}

    @app.post("/api/assets/keyword")
    async def api_add_keyword(payload: AssetKeywordRequest) -> dict[str, Any]:
        raw_parts = re.split(r"[,，;；\r\n]+", payload.keyword)
        seen: set[str] = set()
        items: list[str] = []
        for part in raw_parts:
            kw = part.strip()
            if kw and kw not in seen:
                seen.add(kw)
                items.append(kw)
        if not items:
            raise HTTPException(status_code=400, detail="关键词不能为空")
        inserted_ids: list[int] = []
        with db.connect() as conn:
            lib_row = conn.execute("SELECT id FROM keyword_libraries WHERE id=?", (payload.library_id,)).fetchone()
            lib_id = int(lib_row["id"]) if lib_row else 1
            for kw in items:
                cur = conn.execute("INSERT INTO keywords (library_id, keyword) VALUES (?, ?)", (lib_id, kw))
                inserted_ids.append(int(cur.lastrowid))
        return {"ok": True, "id": inserted_ids[0], "ids": inserted_ids, "added": len(inserted_ids)}

    @app.delete("/api/assets/keyword/{item_id}")
    async def api_delete_keyword(item_id: int) -> dict[str, Any]:
        with db.connect() as conn:
            cur = conn.execute("DELETE FROM keywords WHERE id=?", (item_id,))
        return {"ok": True, "deleted": cur.rowcount}

    @app.put("/api/assets/kb/{kb_id}")
    @app.post("/api/assets/kb/{kb_id}")
    async def api_update_kb(kb_id: int, payload: AssetKbUpdateRequest) -> dict[str, Any]:
        content = payload.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="知识库内容不能为空")
        today = dt.datetime.now().strftime("%Y-%m-%d")
        with db.connect() as conn:
            existing = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="知识库不存在")
            new_name = (payload.name or "").strip() or str(existing["name"])
            new_desc = payload.description if payload.description is not None else str(existing["description"] or "")
            conn.execute(
                "UPDATE knowledge_bases SET name=?, description=?, content=?, updated_at=? WHERE id=?",
                (new_name, new_desc, content, today, kb_id),
            )
        return {"ok": True, "id": kb_id, "name": new_name, "updated_at": today}

    @app.post("/api/baseline/record")
    async def api_baseline_record(payload: BaselineRecordRequest) -> dict[str, Any]:
        engine = payload.engine.strip()
        if not engine:
            raise HTTPException(status_code=400, detail="请选择评测 AI 引擎")

        raw_urls = payload.cited_urls
        clean_urls: list[str] = []
        if isinstance(raw_urls, str):
            clean_urls = [u.strip() for u in re.split(r"[,，\s\r\n]+", raw_urls) if u.strip()]
        elif isinstance(raw_urls, list):
            clean_urls = [str(u).strip() for u in raw_urls if str(u).strip()]

        now_dt = dt.datetime.now()
        run_date = (payload.run_date or "").strip() or now_dt.strftime("%Y-%m-%d")
        created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        cited_json = json.dumps(clean_urls, ensure_ascii=False)
        details_json = json.dumps({"notes": (payload.notes or "").strip()}, ensure_ascii=False)

        norm_targets = {_norm_url(u) for u in clean_urls if _norm_url(u)}
        raw_targets = set(clean_urls)
        matched_rows = 0

        with db.connect() as conn:
            cur = conn.execute(
                """INSERT INTO citation_runs
                   (engine, run_date, our_citation_rate, unprompted_rate, sensitive_accuracy, cited_urls_json, details_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    engine,
                    run_date,
                    float(payload.our_citation_rate),
                    float(payload.unprompted_rate),
                    float(payload.sensitive_accuracy),
                    cited_json,
                    details_json,
                    created_at,
                ),
            )
            run_id = int(cur.lastrowid)

            if clean_urls:
                ledger_rows = conn.execute("SELECT id, url FROM ledger WHERE url IS NOT NULL AND url != ''").fetchall()
                for lr in ledger_rows:
                    lurl = str(lr["url"]).strip()
                    if lurl in raw_targets or _norm_url(lurl) in norm_targets:
                        conn.execute(
                            "UPDATE ledger SET citations = COALESCE(citations, 0) + 1 WHERE id=?",
                            (int(lr["id"]),),
                        )
                        matched_rows += 1

        return {"ok": True, "id": run_id, "matched_citations": matched_rows}

    @app.post("/api/settings")
    async def api_save_settings(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        updated = save_settings(payload)
        browser_engine.cdp_port = int(updated.get("cdp_port") or 9233)
        return {"ok": True, "settings_masked": _mask_settings(updated)}

    @app.post("/api/official/health")
    @app.get("/api/official/health")
    async def api_official_health() -> dict[str, Any]:
        try:
            return await run_in_threadpool(OfficialSitePublisher(load_settings()).check_health)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    res_dir = bundle_resource_dir()
    static_dir = res_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    assets_dir = res_dir / "assets"
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    return app
