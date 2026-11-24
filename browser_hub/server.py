import asyncio
import os
import re
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from playwright.async_api import Page, async_playwright
from pydantic import BaseModel, Field

app = FastAPI(title="GEOFlow Visual Browser Hub", version="1.0.0")
CDP_URL = os.environ.get("CDP_URL", "http://127.0.0.1:9222")
HUB_TOKEN = os.environ.get("BROWSER_HUB_TOKEN", "")
_lock = asyncio.Lock()

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


class OpenTabRequest(BaseModel):
    platform: Optional[str] = None
    url: Optional[str] = None


class PublishRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=40)
    title: str = Field(..., min_length=2, max_length=250)
    content: str = Field(..., min_length=10, max_length=60000)
    action: Literal["draft", "publish"] = "draft"
    editor_url: Optional[str] = None


def verify_token(x_hub_token: Optional[str]) -> None:
    if HUB_TOKEN and x_hub_token != HUB_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized browser hub token")


def clean_title_for_platform(title: str, max_len: int = 30) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    if len(t) <= max_len:
        return t
    # Remove stock code suffix like (000981.SZ) first to preserve core meaning
    t2 = re.sub(r"[（(]000981(?:\.SZ)?[）)]", "", t).strip()
    if len(t2) <= max_len:
        return t2
    return t2[: max_len - 1].rstrip("：:—-·,， ") + "…"


def clean_markdown_to_paragraphs(md: str) -> list[str]:
    """Convert Markdown (including pipe tables & headings) into clean plain paragraphs."""
    lines = md.splitlines()
    paragraphs: list[str] = []
    table_headers: list[str] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            table_headers = []
            continue
        if line.startswith("```"):
            continue
        # Handle Markdown pipe tables cleanly
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
        # Strip headings & inline markdown formatting
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1（\2）", line)
        if line.startswith("- ") or line.startswith("* "):
            line = "• " + line[2:].strip()
        paragraphs.append(line)

    return paragraphs


async def check_login_or_verification_gate(page: Page) -> Optional[str]:
    """Detect login redirects or anti-bot/verification gates WITHOUT attempting to solve them."""
    url = (page.url or "").lower()
    login_indicators = ["/auth/page/login", "/login", "sso.toutiao.com", "passport.", "/sign_in"]
    if any(tok in url for tok in login_indicators):
        return "当前平台尚未登录（或 Cookie 已过期），请点开右上角「云端浏览器窗口」扫码登录一次。"

    # Check common visible verification prompts without interacting with them
    gate_selectors = [
        "text=扫码验证",
        "text=请完成安全验证",
        "text=向右拖动滑块",
        "text=接收短信验证码",
        ".captcha_verify_container",
        "#secsdk-captcha-drag-wrapper",
    ]
    for sel in gate_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                return "平台弹出安全验证，已为您保留在云端浏览器画面中，请点开「云端浏览器窗口」手动确认一下。"
        except Exception:
            pass
    return None


async def publish_toutiao(page: Page, title: str, paragraphs: list[str], action: str) -> dict:
    await page.goto(PLATFORM_URLS["toutiao"], wait_until="domcontentloaded", timeout=35000)
    await page.wait_for_timeout(3000)
    await page.bring_to_front()

    gate = await check_login_or_verification_gate(page)
    if gate:
        return {"ok": False, "status": "need_login", "message": gate, "editor_url": page.url}

    # Dismiss benign onboarding tooltips if any (never CAPTCHAs)
    for dismiss_sel in ["button:has-text('我知道了')", "button:has-text('跳过')"]:
        try:
            btn = page.locator(dismiss_sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=1500)
        except Exception:
            pass

    short_title = clean_title_for_platform(title, 30)
    title_filled = False
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
            title_filled = True
            break

    body_filled = False
    body_text = "\n\n".join(paragraphs)
    for b_sel in [".ProseMirror", "[contenteditable='true']"]:
        loc = page.locator(b_sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.insert_text(body_text)
            body_filled = True
            break

    if not title_filled or not body_filled:
        return {
            "ok": False,
            "status": "editor_mismatch",
            "message": "已打开头条页面，但未定位到标题或正文输入框，请点开「云端浏览器窗口」查看当前画面。",
            "editor_url": page.url,
        }

    # Select "无封面" if available so cover selection doesn't block
    for cov_sel in ["label:has-text('无封面')", "span:has-text('无封面')"]:
        try:
            c_loc = page.locator(cov_sel).first
            if await c_loc.count() > 0 and await c_loc.is_visible():
                await c_loc.click(timeout=1500)
                break
        except Exception:
            pass

    await page.wait_for_timeout(2500)

    if action == "draft":
        for draft_sel in ["button:has-text('草稿')", "span:has-text('存草稿')"]:
            try:
                d_btn = page.locator(draft_sel).first
                if await d_btn.count() > 0 and await d_btn.is_visible():
                    await d_btn.click(timeout=2000)
                    break
            except Exception:
                pass
        return {
            "ok": True,
            "status": "draft_saved",
            "message": f"今日头条已自动填好标题与正文并存入草稿（标题：{short_title}）",
            "url": "",
            "editor_url": page.url,
        }

    # action == "publish": click 预览并发布 -> 确认发布
    clicked_pub = False
    for pub_sel in [
        "button:has-text('预览并发布')",
        "button:has-text('发布')",
        ".publish-btn-last",
    ]:
        p_btn = page.locator(pub_sel).last
        if await p_btn.count() > 0 and await p_btn.is_visible():
            await p_btn.click(timeout=3000)
            clicked_pub = True
            break

    await page.wait_for_timeout(2000)
    gate_after = await check_login_or_verification_gate(page)
    if gate_after:
        return {"ok": False, "status": "need_verify", "message": gate_after, "editor_url": page.url}

    for confirm_sel in ["button:has-text('确认发布')", "button:has-text('确定')"]:
        c_btn = page.locator(confirm_sel).last
        if await c_btn.count() > 0 and await c_btn.is_visible():
            await c_btn.click(timeout=3000)
            await page.wait_for_timeout(3500)
            break

    gate_final = await check_login_or_verification_gate(page)
    if gate_final:
        return {"ok": False, "status": "need_verify", "message": gate_final, "editor_url": page.url}

    # Check content management list for live/reviewing URL
    published_url = ""
    try:
        await page.goto("https://mp.toutiao.com/profile_v4/manage/content/all", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2500)
        link = page.locator("a[href*='toutiao.com/item/'], a[href*='toutiao.com/article/']").first
        if await link.count() > 0:
            href = await link.get_attribute("href") or ""
            if href.startswith("//"):
                href = "https:" + href
            published_url = href
    except Exception:
        pass

    if clicked_pub:
        return {
            "ok": True,
            "status": "published" if published_url else "submitted",
            "message": "今日头条已自动提交发布" + (f"（{published_url}）" if published_url else "（平台审核中，已在云端浏览器打开作品管理页）"),
            "url": published_url,
            "editor_url": page.url,
        }

    return {
        "ok": True,
        "status": "draft_saved",
        "message": "今日头条已填好标题与正文，请点开云端浏览器确认最后一步发布。",
        "url": "",
        "editor_url": page.url,
    }


async def publish_generic_portal(page: Page, platform: str, target_url: str, title: str, paragraphs: list[str]) -> dict:
    await page.goto(target_url, wait_until="domcontentloaded", timeout=35000)
    await page.wait_for_timeout(3000)
    await page.bring_to_front()

    gate = await check_login_or_verification_gate(page)
    if gate:
        return {"ok": False, "status": "need_login", "message": gate, "editor_url": page.url}

    short_title = clean_title_for_platform(title, 38)
    title_filled = False
    for t_sel in [
        "input[placeholder*='标题']",
        "textarea[placeholder*='标题']",
        "input[placeholder*='请输入标题']",
    ]:
        loc = page.locator(t_sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await loc.fill(short_title)
            title_filled = True
            break

    body_filled = False
    body_text = "\n\n".join(paragraphs)
    for b_sel in ["[contenteditable='true']", ".ql-editor", ".ProseMirror", "textarea"]:
        loc = page.locator(b_sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.keyboard.insert_text(body_text)
            body_filled = True
            break

    if title_filled or body_filled:
        return {
            "ok": True,
            "status": "draft_saved",
            "message": f"{platform} 已在云端浏览器自动填入草稿，可点开云端浏览器核对发布",
            "url": "",
            "editor_url": page.url,
        }
    return {
        "ok": False,
        "status": "opened_only",
        "message": f"已在云端浏览器打开 {platform} 发布页，请点开云端浏览器检查登录状态或手动确认",
        "url": "",
        "editor_url": page.url,
    }


@app.get("/health")
async def health():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            ctx = browser.contexts[0] if browser.contexts else None
            tabs = [pg.url for pg in (ctx.pages if ctx else [])]
            return {"ok": True, "cdp_ready": True, "tab_count": len(tabs), "tabs": tabs[:10]}
    except Exception as e:
        return {"ok": False, "cdp_ready": False, "error": str(e)}


@app.post("/open-platform")
async def open_platform(req: OpenTabRequest, x_hub_token: Optional[str] = Header(default=None)):
    verify_token(x_hub_token)
    target = req.url or PLATFORM_URLS.get(req.platform or "", "https://mp.toutiao.com/profile_v4/graphic/publish")
    async with _lock:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await ctx.new_page()
            await page.goto(target, wait_until="domcontentloaded", timeout=30000)
            await page.bring_to_front()
            return {"ok": True, "url": page.url}


@app.post("/publish")
async def publish_article(req: PublishRequest, x_hub_token: Optional[str] = Header(default=None)):
    verify_token(x_hub_token)
    paragraphs = clean_markdown_to_paragraphs(req.content)
    platform = req.platform.lower().strip()
    target_url = req.editor_url or PLATFORM_URLS.get(platform, "https://mp.toutiao.com/profile_v4/graphic/publish")

    async with _lock:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
            # Reuse existing blank/login tab if fewer than 6 tabs, else open new tab
            if len(ctx.pages) >= 8:
                try:
                    await ctx.pages[1].close()
                except Exception:
                    pass
            page = await ctx.new_page()
            if platform == "toutiao":
                return await publish_toutiao(page, req.title, paragraphs, req.action)
            return await publish_generic_portal(page, platform, target_url, req.title, paragraphs)
