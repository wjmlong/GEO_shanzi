"""Push Sensteed /insights/ URLs to IndexNow (Bing/DeepSeek) and Baidu Link Submit API.

Reads BAIDU_PUSH_TOKEN from environment or project-root .env.local (gitignored).
"""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE_HOST = "www.sensteed.com"
MAIN_SITE = "https://www.sensteed.com"
SITEMAP_URL = "https://www.sensteed.com/insights/sitemap.xml"
INDEXNOW_KEY = "8f4d9e2a6c1b7f3e5a0d8c4b2e6f1a9d"
INDEXNOW_KEY_LOCATION = f"https://{SITE_HOST}/{INDEXNOW_KEY}.txt"


def load_local_env() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env.local"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def fetch_insights_urls() -> list[str]:
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(SITEMAP_URL, timeout=15, context=ctx) as resp:
        xml = resp.read().decode("utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def push_indexnow(urls: list[str]) -> dict:
    payload = json.dumps(
        {
            "host": SITE_HOST,
            "key": INDEXNOW_KEY,
            "keyLocation": INDEXNOW_KEY_LOCATION,
            "urlList": urls,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return {"ok": resp.status in (200, 202), "status": resp.status}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "body": exc.read().decode("utf-8", "replace")}


def _baidu_post(api_url: str, batch: list[str]) -> tuple[int, str]:
    data = "\n".join(batch).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "text/plain", "User-Agent": "sensteed-geo-pusher/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def push_baidu(urls: list[str], token: str) -> dict:
    if not token:
        return {"ok": False, "skipped": True, "reason": "BAIDU_PUSH_TOKEN not set"}
    api_url = f"http://data.zz.baidu.com/urls?site={MAIN_SITE}&token={token}"
    code, body = _baidu_post(api_url, urls)
    if code == 200:
        return {"ok": True, "mode": "batch", "status": code, "response": json.loads(body)}

    # If batch exceeded remaining quota (e.g. remain < len(urls)), try newest article URLs 1-by-1
    if "over quota" in body and len(urls) > 1:
        article_urls = [u for u in urls if "/article/" in u] + [u for u in urls if "/article/" not in u]
        pushed = []
        last_resp = body
        for u in article_urls:
            c1, b1 = _baidu_post(api_url, [u])
            last_resp = b1
            if c1 == 200:
                pushed.append(u)
            else:
                break
        if pushed:
            return {"ok": True, "mode": "single_fallback", "pushed_count": len(pushed), "pushed": pushed, "last": last_resp}

    return {"ok": False, "status": code, "response": body}


def main() -> int:
    load_local_env()
    urls = fetch_insights_urls()
    print(f"Fetched {len(urls)} URLs from {SITEMAP_URL}")
    in_res = push_indexnow(urls)
    print("IndexNow ->", json.dumps(in_res, ensure_ascii=False))
    bd_token = os.environ.get("BAIDU_PUSH_TOKEN", "").strip()
    bd_res = push_baidu(urls, bd_token)
    print("Baidu API ->", json.dumps(bd_res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
