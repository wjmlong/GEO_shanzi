"""打开一个有界面的浏览器，由你手动登录东方财富（验证码也由你自己完成），保存登录状态。

用法：
  python3 login.py          # 弹出浏览器，登录完成并能正常打开股吧帖子后，直接关掉浏览器窗口
  python3 login.py --check  # 用保存的登录状态打开一个帖子，看能不能拿到评论

eastmoney_state.json 里是登录 cookie，等同于账号密码，不要外传。
"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
STATE = HERE / "eastmoney_state.json"
START_URL = "https://guba.eastmoney.com/list,000981.html"
CHECK_URL = "https://guba.eastmoney.com/news,000981,1782590113.html"


def login():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--no-proxy-server"])
        context = browser.new_context()
        page = context.new_page()
        page.goto(START_URL, wait_until="domcontentloaded")
        print("请在弹出的浏览器里登录东方财富。登录后随便点开一个帖子确认能看到评论，然后关掉浏览器窗口。")
        page.wait_for_event("close", timeout=0)
        context.storage_state(path=str(STATE))
        os.chmod(STATE, 0o600)
        browser.close()
    print(f"登录状态已保存到 {STATE}")


def check():
    if not STATE.exists():
        sys.exit("还没有登录状态，先运行 python3 login.py")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-proxy-server"])
        context = browser.new_context(storage_state=str(STATE))
        page = context.new_page()
        replies = []

        def on_response(r):
            if "Reply" in r.url:
                try:
                    replies.append((r.url.split("?")[0], r.text()[:300]))
                except Exception as e:
                    replies.append((r.url, f"ERR {e}"))

        page.on("response", on_response)
        page.goto(CHECK_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)
        title = page.title()
        browser.close()
    print("页面标题：", title)
    if "身份核实" in title:
        print("仍然是身份核实页，登录状态没有生效或已过期")
    for url, body in replies:
        print(url, "\n  ", body)
    if not replies:
        print("没有捕获到评论接口请求")


if __name__ == "__main__":
    check() if "--check" in sys.argv else login()
