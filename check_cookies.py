"""检查手动导出的 Cookie 是否有效（能不能拿到评论）。

前提：你已经在 Windows 浏览器里登录东方财富，并用扩展导出 cookie 到 eastmoney_cookies.json。
步骤见 manual_login_guide.md
"""
import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
COOKIES_FILE = HERE / "eastmoney_cookies.json"
CHECK_URL = "https://guba.eastmoney.com/news,000981,1782590113.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def main():
    if not COOKIES_FILE.exists():
        sys.exit(f"找不到 {COOKIES_FILE}\n请先按照 manual_login_guide.md 导出 cookie")

    # 读浏览器扩展导出的 JSON（数组格式）
    raw = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        sys.exit("Cookie 文件格式不对，应该是一个 JSON 数组")

    # 转成 requests 能用的 dict
    cookies = {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
    if not cookies:
        sys.exit("Cookie 文件里没有有效的 name/value 对")

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers["User-Agent"] = UA

    print(f"从 {COOKIES_FILE} 读到 {len(cookies)} 条 cookie，测试中...")
    resp = session.get(CHECK_URL, timeout=30)
    page = resp.text

    if "身份核实" in page:
        print("❌ 仍然是身份核实页，cookie 可能无效或已过期")
        print("   重新在浏览器里登录，导出新的 cookie")
        sys.exit(1)

    # 看看能不能拿到评论接口（页面加载后会有 JS 请求）
    # 这里简化：直接看页面标题
    if "<title>" in page:
        title_start = page.find("<title>") + 7
        title_end = page.find("</title>", title_start)
        title = page[title_start:title_end] if title_end > title_start else "无法提取"
        print(f"✓ 页面标题：{title}")

    # 真正要抓评论，得解析页面里的 post_id 再调评论接口
    # 这里只是确认登录状态，先不实现完整抓取
    if len(page) > 5000:  # 正常帖子页面应该有几十 KB
        print("✓ Cookie 有效，页面内容完整")
        print(f"下一步：运行 python3 monitor.py collect --pages 1 测试能不能抓到帖子列表")
    else:
        print(f"⚠ 页面太短（{len(page)} 字节），可能被重定向或限流了")


if __name__ == "__main__":
    main()
