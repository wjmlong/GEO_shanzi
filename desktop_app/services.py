from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import json
import pathlib
import re
import subprocess
import time
import urllib.parse
import uuid
from typing import Any

import httpx
import markdown as md_lib
from playwright.async_api import Page, async_playwright

from desktop_app.db import GeoLocalDB, app_root_dir, data_dir

PLATFORM_URLS = {
    "toutiao": "https://mp.toutiao.com/profile_v4/graphic/publish",
    "sohu": "https://mp.sohu.com/suc-ce/article/publish",
    "netease": "https://mp.163.com/subscribe_v4/index.html#/article-publish",
    "eastmoney": "https://mp.eastmoney.com/collect/pc_article/index.html#/",
    "ths": "https://basic.10jqka.com.cn/000981/",
    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
    "wechat": "https://mp.weixin.qq.com/",
    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
    "doubao": "https://www.doubao.com/chat/",
    "deepseek": "https://chat.deepseek.com/",
}


def find_portable_chromium() -> pathlib.Path | None:
    """Locate bundled portable Chromium inside ./browsers/ (or dev dist/ShanziGEO/browsers/)."""
    roots = [
        app_root_dir() / "browsers",
        app_root_dir() / "dist" / "ShanziGEO" / "browsers",
    ]
    for r in roots:
        if r.exists():
            matches = sorted(r.rglob("chrome.exe"), reverse=True)
            for m in matches:
                if "headless_shell" not in str(m).lower():
                    return m
            if matches:
                return matches[0]
    # Fallback to common local browsers only if portable folder absent
    for fb in [
        pathlib.Path(r"E:\Utils\CentBrowser\CentBrowser\Application\chrome.exe"),
        pathlib.Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        pathlib.Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]:
        if fb.exists():
            return fb
    return None


def clean_title_for_platform(title: str, max_len: int = 30) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    if len(t) <= max_len:
        return t
    t2 = re.sub(r"[（(]000981(?:\.SZ)?[）)]", "", t).strip()
    if len(t2) <= max_len:
        return t2
    return t2[: max_len - 1].rstrip("：:—-·,， ") + "…"


def clean_markdown_to_paragraphs(md_text: str) -> list[str]:
    lines = md_text.splitlines()
    paragraphs: list[str] = []
    table_headers: list[str] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            table_headers = []
            continue
        if line.startswith("```"):
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
                continue
            if not table_headers:
                table_headers = cells
            else:
                parts = []
                for idx, val in enumerate(cells):
                    if not val:
                        continue
                    if idx == 0:
                        parts.append(f"• {val}")
                    elif idx < len(table_headers) and table_headers[idx]:
                        parts.append(f"{table_headers[idx]}：{val}")
                    else:
                        parts.append(val)
                if parts:
                    paragraphs.append(" ｜ ".join(parts))
            continue

        table_headers = []
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1（\2）", line)
        if line.startswith("- ") or line.startswith("* "):
            line = "• " + line[2:].strip()
        paragraphs.append(line)

    return paragraphs


class OfficialSitePublisher:
    """1-second signed HMAC publisher to https://www.sensteed.com/insights/."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.base_url = str(settings.get("official_endpoint_url") or "https://www.sensteed.com/insights").rstrip("/")
        self.key_id = str(settings.get("official_key_id") or "").strip()
        self.secret = str(settings.get("official_secret") or "").strip()

    def _headers(self, method: str, path: str, body: str, event: str, idem_key: str) -> dict[str, str]:
        ts = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
        nonce = str(uuid.uuid4())
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        signing_str = f"{method.upper()}\n{path}\n{ts}\n{nonce}\n{body_hash}"
        sig = hmac.new(self.secret.encode("utf-8"), signing_str.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-GEOFlow-Key-Id": self.key_id,
            "X-GEOFlow-Timestamp": ts,
            "X-GEOFlow-Nonce": nonce,
            "X-GEOFlow-Idempotency-Key": idem_key,
            "X-GEOFlow-Body-SHA256": body_hash,
            "X-GEOFlow-Signature": sig,
            "X-GEOFlow-Event": event,
        }

    def check_health(self) -> dict[str, Any]:
        if not self.key_id or not self.secret:
            return {"ok": False, "error": "尚未配置官网直发密钥"}
        path = "/geoflow-agent/v1/health"
        body = "{}"
        headers = self._headers("GET", path, body, "health.check", f"health-{int(time.time())}")
        with httpx.Client(timeout=10.0, verify=True) as client:
            resp = client.get(self.base_url + path, headers=headers)
            if resp.status_code == 404:
                resp = client.get(self.base_url + "/index.php" + path, headers=headers)
            if resp.status_code >= 400:
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            return data if isinstance(data, dict) else {"ok": True}

    def publish_article(self, article: dict[str, Any]) -> dict[str, Any]:
        if not self.key_id or not self.secret:
            raise RuntimeError("尚未在「系统配置」填写官网直发 Key ID 与密钥")
        now_iso = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
        content_md = str(article.get("content") or "")
        content_html = md_lib.markdown(content_md, extensions=["tables", "fenced_code"])
        plain = re.sub(r"[#*`>\-\r\n]+", " ", content_md).strip()
        excerpt = str(article.get("excerpt") or plain[:140])
        slug = str(article.get("slug") or f"post-{uuid.uuid4().hex[:8]}")

        payload = {
            "version": "1.0",
            "source": "shanzigeo-desktop",
            "event": "article.publish",
            "article": {
                "id": int(article.get("id") or int(time.time())),
                "title": str(article["title"]),
                "slug": slug,
                "excerpt": excerpt,
                "content": content_md,
                "content_format": "markdown",
                "content_html": content_html,
                "hero_image_url": None,
                "keywords": str(article.get("keywords") or "山子高科,000981,邦奇动力,艾尔希ARC,半导体先进封装材料"),
                "meta_description": excerpt,
                "status": "published",
                "is_featured": False,
                "is_hot": False,
                "published_at": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
                "category": {"id": 1, "name": "产业观察", "slug": "insights"},
                "author": {"id": 1, "name": "山子高科产业观察"},
                "task": None,
            },
            "assets": [],
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        path = "/geoflow-agent/v1/articles"
        idem = f"desk-{slug}-{int(time.time())}"
        headers = self._headers("POST", path, body, "article.publish", idem)

        with httpx.Client(timeout=20.0, verify=True) as client:
            resp = client.post(self.base_url + path, content=body.encode("utf-8"), headers=headers)
            if resp.status_code == 404:
                resp = client.post(self.base_url + "/index.php" + path, content=body.encode("utf-8"), headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"官网返回 HTTP {resp.status_code}: {resp.text[:200]}")
            res = resp.json()
            remote_url = str(res.get("remote_url") or res.get("url") or f"{self.base_url}/article/{slug}.html")
            return {"ok": True, "remote_url": remote_url, "raw": res}


class PortableBrowserEngine:
    """0-Token deterministic Playwright CDP controller over the bundled portable Chromium."""

    def __init__(self, cdp_port: int = 9233) -> None:
        self.cdp_port = cdp_port
        self._lock = asyncio.Lock()
        self._proc: subprocess.Popen | None = None

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.cdp_port}"

    @property
    def profile_dir(self) -> pathlib.Path:
        p = data_dir() / "chrome-profile"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def is_running(self) -> bool:
        try:
            with httpx.Client(timeout=0.8, trust_env=False) as client:
                return client.get(f"{self.cdp_url}/json/version").status_code == 200
        except Exception:
            return False

    def ensure_started(self, initial_urls: list[str] | None = None) -> dict[str, Any]:
        chrome_bin = find_portable_chromium()
        if not chrome_bin:
            return {"ok": False, "error": "未找到内置便携 Chromium（browsers/chrome.exe）"}

        if not self.is_running():
            # Clean stale lock files if browser was previously force-closed
            for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                lp = self.profile_dir / lock_name
                if lp.exists():
                    try:
                        lp.unlink()
                    except OSError:
                        pass

            urls = initial_urls or [
                PLATFORM_URLS["toutiao"],
                PLATFORM_URLS["sohu"],
                PLATFORM_URLS["eastmoney"],
                PLATFORM_URLS["doubao"],
                PLATFORM_URLS["deepseek"],
            ]
            args = [
                str(chrome_bin),
                f"--user-data-dir={self.profile_dir}",
                f"--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={self.cdp_port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                *urls,
            ]
            self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(25):
                if self.is_running():
                    break
                time.sleep(0.3)

        return {"ok": self.is_running(), "chrome_bin": str(chrome_bin), "profile_dir": str(self.profile_dir)}

    async def open_url(self, url: str) -> dict[str, Any]:
        st = self.ensure_started([url])
        if not st.get("ok"):
            return st
        async with self._lock:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(self.cdp_url)
                ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await ctx.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.bring_to_front()
                return {"ok": True, "url": page.url}

    @staticmethod
    async def _check_gate(page: Page) -> str | None:
        url = (page.url or "").lower()
        if any(k in url for k in ["/auth/page/login", "/login", "sso.toutiao.com", "passport.", "/sign_in"]):
            return "该平台尚未登录，已在内置浏览器打开登录页，请扫码登录一次（Cookie 将自动永久保存）。"
        for sel in [
            "text=扫码验证",
            "text=请完成安全验证",
            "text=向右拖动滑块",
            "text=接收短信验证码",
            ".captcha_verify_container",
            "#secsdk-captcha-drag-wrapper",
        ]:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return "平台弹出安全验证，已在内置浏览器窗口保留当前画面，请手动点一下完成验证。"
            except Exception:
                pass
        return None

    async def publish_article(self, platform: str, title: str, content: str, action: str, editor_url: str = "") -> dict[str, Any]:
        target = editor_url or PLATFORM_URLS.get(platform, PLATFORM_URLS["toutiao"])
        st = self.ensure_started([target])
        if not st.get("ok"):
            return st

        paragraphs = clean_markdown_to_paragraphs(content)
        async with self._lock:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(self.cdp_url)
                ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await ctx.new_page()
                if platform == "toutiao":
                    return await self._publish_toutiao(page, title, paragraphs, action)
                return await self._publish_generic(page, platform, target, title, paragraphs)

    async def fill_desktop_draft(self, port: int, target_id: str, url: str, title: str, content: str) -> dict[str, Any]:
        """Fill the page the operator has open. Never create a new tab or submit a form."""
        body = "\n\n".join(clean_markdown_to_paragraphs(content))
        if not title.strip() or not body.strip():
            return {"ok": False, "message": "请先填写标题与正文。"}
        async with self._lock:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=8000)
                for context in browser.contexts:
                    for page in context.pages:
                        if page.url != url:
                            continue
                        session = await context.new_cdp_session(page)
                        try:
                            info = await session.send("Target.getTargetInfo")
                        finally:
                            await session.detach()
                        if info["targetInfo"]["targetId"] == target_id:
                            return await self._fill_current_editor(page, title.strip(), body)
        return {"ok": False, "message": "右栏页面已切换，请在当前编辑页重新点填稿。"}

    async def _fill_current_editor(self, page: Page, title: str, body: str) -> dict[str, Any]:
        if await self._check_gate(page):
            return {"ok": False, "message": "请先在右栏完成平台登录或验证。"}
        title_fields = page.locator("input[placeholder*='标题']:visible, textarea[placeholder*='标题']:visible")
        body_fields = page.locator(".ProseMirror[contenteditable='true']:visible, .ql-editor[contenteditable='true']:visible, [contenteditable='true']:visible, textarea:not([placeholder*='标题']):visible")
        if await title_fields.count() != 1 or await body_fields.count() != 1:
            return {"ok": False, "message": "请打开平台发稿编辑页，确认有一个标题栏和一个正文栏。"}
        if urllib.parse.urlsplit(page.url).hostname == "mp.toutiao.com":
            title = clean_title_for_platform(title, 30)
        await title_fields.fill(title, timeout=5000)
        await body_fields.fill(body, timeout=5000)
        return {"ok": True, "message": "标题和正文已填入右栏。你可以继续编辑。"}

    async def _publish_toutiao(self, page: Page, title: str, paragraphs: list[str], action: str) -> dict[str, Any]:
        await page.goto(PLATFORM_URLS["toutiao"], wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(2800)
        await page.bring_to_front()

        gate = await self._check_gate(page)
        if gate:
            return {"ok": False, "status": "need_login", "message": gate}

        for dismiss_sel in ["button:has-text('我知道了')", "button:has-text('跳过')"]:
            try:
                btn = page.locator(dismiss_sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=1200)
            except Exception:
                pass

        short_title = clean_title_for_platform(title, 30)
        title_ok = False
        for t_sel in [
            "textarea[placeholder*='请输入文章标题']",
            "textarea[placeholder*='标题']",
            "input[placeholder*='标题']",
            ".editor-title textarea",
        ]:
            loc = page.locator(t_sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                await loc.fill(short_title)
                title_ok = True
                break

        body_ok = False
        body_text = "\n\n".join(paragraphs)
        for b_sel in [".ProseMirror", "[contenteditable='true']"]:
            loc = page.locator(b_sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await page.keyboard.insert_text(body_text)
                body_ok = True
                break

        if not title_ok or not body_ok:
            return {"ok": False, "status": "editor_mismatch", "message": "已打开头条编辑页，请在弹出的内置浏览器窗口检查当前画面。"}

        for cov_sel in ["label:has-text('无封面')", "span:has-text('无封面')"]:
            try:
                c_loc = page.locator(cov_sel).first
                if await c_loc.count() > 0 and await c_loc.is_visible():
                    await c_loc.click(timeout=1500)
                    break
            except Exception:
                pass

        await page.wait_for_timeout(2200)
        if action == "draft":
            for draft_sel in ["button:has-text('草稿')", "span:has-text('存草稿')"]:
                try:
                    d_btn = page.locator(draft_sel).first
                    if await d_btn.count() > 0 and await d_btn.is_visible():
                        await d_btn.click(timeout=1800)
                        break
                except Exception:
                    pass
            return {
                "ok": True,
                "status": "draft_saved",
                "message": f"今日头条已 0 Token 自动填好标题与正文并存草稿（{short_title}）",
                "url": "",
            }

        clicked_pub = False
        for pub_sel in ["button:has-text('预览并发布')", "button:has-text('发布')", ".publish-btn-last"]:
            p_btn = page.locator(pub_sel).last
            if await p_btn.count() > 0 and await p_btn.is_visible():
                await p_btn.click(timeout=3000)
                clicked_pub = True
                break

        await page.wait_for_timeout(1800)
        gate2 = await self._check_gate(page)
        if gate2:
            return {"ok": False, "status": "need_verify", "message": gate2}

        for confirm_sel in ["button:has-text('确认发布')", "button:has-text('确定')"]:
            c_btn = page.locator(confirm_sel).last
            if await c_btn.count() > 0 and await c_btn.is_visible():
                await c_btn.click(timeout=3000)
                await page.wait_for_timeout(3200)
                break

        gate3 = await self._check_gate(page)
        if gate3:
            return {"ok": False, "status": "need_verify", "message": gate3}

        pub_url = ""
        try:
            await page.goto("https://mp.toutiao.com/profile_v4/manage/content/all", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2500)
            link = page.locator("a[href*='toutiao.com/item/'], a[href*='toutiao.com/article/']").first
            if await link.count() > 0:
                href = await link.get_attribute("href") or ""
                pub_url = ("https:" + href) if href.startswith("//") else href
        except Exception:
            pass

        return {
            "ok": True,
            "status": "published" if pub_url else ("submitted" if clicked_pub else "draft_saved"),
            "message": "今日头条已自动提交发布" + (f"（{pub_url}）" if pub_url else "（审核中，可在内置浏览器作品管理查看）"),
            "url": pub_url,
        }

    async def _publish_generic(self, page: Page, platform: str, target_url: str, title: str, paragraphs: list[str]) -> dict[str, Any]:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(2800)
        await page.bring_to_front()

        gate = await self._check_gate(page)
        if gate:
            return {"ok": False, "status": "need_login", "message": gate}

        short_title = clean_title_for_platform(title, 38)
        t_ok = False
        for t_sel in ["input[placeholder*='标题']", "textarea[placeholder*='标题']", "input[placeholder*='请输入标题']"]:
            loc = page.locator(t_sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                await loc.fill(short_title)
                t_ok = True
                break

        b_ok = False
        body_text = "\n\n".join(paragraphs)
        for b_sel in ["[contenteditable='true']", ".ql-editor", ".ProseMirror", "textarea"]:
            loc = page.locator(b_sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click()
                await page.keyboard.insert_text(body_text)
                b_ok = True
                break

        if t_ok or b_ok:
            return {"ok": True, "status": "draft_saved", "message": f"{platform} 已在内置浏览器 0 Token 自动填入草稿，请核对后点发布", "url": ""}
        return {"ok": False, "status": "opened_only", "message": f"已在内置浏览器打开 {platform} 发布页，请检查登录状态或确认编辑框", "url": ""}


class AiComplianceAndWriterService:
    """Calls OpenAI-compatible LLM endpoint for KB-grounded article writing & compliance scoring."""

    def __init__(self, db: GeoLocalDB, settings: dict[str, Any]) -> None:
        self.db = db
        self.api_url = str(settings.get("llm_api_url") or "").rstrip("/")
        self.model_id = str(settings.get("llm_model_id") or "deepseek-v4.1-flash").strip()
        self.api_key = str(settings.get("llm_api_key") or "").strip()

    def _ensure_ready(self) -> None:
        if not self.api_url or not self.api_key:
            raise RuntimeError("请先在「资产库与配置 → 系统配置」填写大模型 API 地址与密钥")

    def _kb_text(self, kb_ids: list[int], max_each: int = 3600) -> str:
        with self.db.connect() as conn:
            placeholders = ",".join("?" for _ in kb_ids)
            rows = conn.execute(f"SELECT id, name, content FROM knowledge_bases WHERE id IN ({placeholders}) ORDER BY id", kb_ids).fetchall()
        return "\n\n".join(f"【{r['name']}】\n{str(r['content'])[:max_each]}" for r in rows)

    def _prompt_text(self, prompt_id: int) -> str:
        with self.db.connect() as conn:
            row = conn.execute("SELECT content FROM prompts WHERE id=?", (prompt_id,)).fetchone()
        return str(row["content"]) if row else ""

    def generate_article(self, topic_title: str, style: str = "long") -> dict[str, Any]:
        self._ensure_ready()
        prompt_map = {"long": 7, "qa": 8, "douyin": 9}
        pid = prompt_map.get(style, 7)
        tpl = self._prompt_text(pid)
        kbs = self._kb_text([1, 2, 3], max_each=3500)

        sys_prompt = (
            "你是山子高科技股份有限公司（000981.SZ）官方产业内容主笔。"
            "必须100%严格依据下方【官方事实知识库】撰写，严禁编造任何未披露业绩、产能、客户名单或预测股价，"
            "严禁使用ST银亿等过时称谓，所有财务与经营数据必须注明法定定期报告或公告编号及披露日期。"
            "直接输出完整 Markdown 正文（不要输出多余寒暄）。"
        )
        user_prompt = (
            f"=== 写作模板与合规准则 ===\n{tpl[:3200]}\n\n"
            f"=== 山子高科官方事实知识库（唯一事实来源） ===\n{kbs}\n\n"
            f"=== 本篇指定题目 ===\n{topic_title}\n\n请开始撰写："
        )
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                f"{self.api_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model_id,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"模型调用失败 (HTTP {resp.status_code}): {resp.text[:200]}")
            text = str(resp.json()["choices"][0]["message"]["content"]).strip()
            return {"ok": True, "title": topic_title, "content": text}

    def inspect_article(self, title: str, content: str) -> dict[str, Any]:
        self._ensure_ready()
        rule_tpl = self._prompt_text(10)
        kbs = self._kb_text([2, 3], max_each=3400)

        sys_prompt = (
            "你是山子高科（000981.SZ）上市公司信披合规与 GEO 内容质量评审官。"
            "请严格依据下方官方事实知识库与质检规则，对稿件客观评分，给出清晰易懂的打分理由、4个维度分项打分，以及逐条扣分原因与修改建议。\n\n"
            "【输出格式强制要求】仅输出合法 JSON（不要 Markdown 代码块包裹），结构如下：\n"
            '{"score": 88, "passed": true, "summary": "一段清晰易懂的总评与核心打分理由", '
            '"dimensions": ['
            '{"name": "事实与公告一致性", "score": 90, "comment": "简短评价"},'
            '{"name": "信披与广告法合规", "score": 92, "comment": "简短评价"},'
            '{"name": "业务与品牌锚点", "score": 85, "comment": "简短评价"},'
            '{"name": "GEO结构与AI易抓度", "score": 85, "comment": "简短评价"}'
            '], "issues": [{"severity": "high|medium|low", "title": "问题简述", "quote": "原文片段", "reason": "扣分理由", "suggestion": "具体修改建议"}]}'
        )
        user_prompt = (
            f"=== 质检规则参考 ===\n{rule_tpl[:2400]}\n\n"
            f"=== 山子高科官方事实知识库（唯一准绳） ===\n{kbs}\n\n"
            f"=== 待评测文章 ===\n标题：{title}\n\n正文：\n{content[:8500]}"
        )

        with httpx.Client(timeout=70.0) as client:
            resp = client.post(
                f"{self.api_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model_id,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"模型调用失败 (HTTP {resp.status_code})")
            raw = str(resp.json()["choices"][0]["message"]["content"]).strip()

        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S) or re.search(r"(\{.*\})", raw, re.S)
        clean = m.group(1) if m else raw
        try:
            parsed = json.loads(clean)
            score = max(0, min(100, int(parsed.get("score", 80))))
            return {
                "ok": True,
                "score": score,
                "passed": score >= 85,
                "summary": str(parsed.get("summary") or ""),
                "dimensions": parsed.get("dimensions") if isinstance(parsed.get("dimensions"), list) else [],
                "issues": parsed.get("issues") if isinstance(parsed.get("issues"), list) else [],
            }
        except Exception:
            return {"ok": True, "score": 80, "passed": False, "summary": raw[:600], "dimensions": [], "issues": []}
