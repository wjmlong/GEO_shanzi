"""东方财富股吧采集：列表页 + 帖子正文，存 SQLite。

只访问公开页面，请求之间随机间隔几秒。一旦遇到“身份核实”验证页立即停止，
不尝试绕过，等限制自动解除后再跑。
"""
import hashlib
import html
import json
import random
import re
import sqlite3
import time
from datetime import datetime, timedelta

import requests

from store import LLM_COLUMNS, migrate, save_cursor, unchanged_post

LIST_URL = "https://guba.eastmoney.com/list,{code}_{page}.html"
POST_URL = "https://guba.eastmoney.com/news,{code},{post_id}.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


PLATFORM = "eastmoney"


class Blocked(Exception):
    """东方财富返回了身份核实页。"""


def make_session(use_proxy=False):
    s = requests.Session()
    s.trust_env = use_proxy  # WSL 里的 http_proxy 指向的代理目前不可用，默认直连
    s.headers["User-Agent"] = UA
    return s


def connect(db_path):
    db = sqlite3.connect(db_path)
    migrate(db)
    return db


def _extract_json(page, var_name):
    i = page.find(f"var {var_name}")
    if i < 0:
        if "身份核实" in page:
            raise Blocked()
        raise ValueError(f"页面里没有 {var_name}")
    obj, _ = json.JSONDecoder().raw_decode(page, page.find("{", i))
    return obj


def _clean(content_html):
    text = re.sub(r"<[^>]+>", " ", content_html or "")
    text = re.sub(r"\$[^$]{1,30}\$", " ", html.unescape(text))  # 去掉 $山子高科(SZ000981)$
    return re.sub(r"\s+", " ", text).strip()


def _get(session, url):
    time.sleep(random.uniform(3, 6))
    r = session.get(url, timeout=15)
    r.raise_for_status()
    return r.text


def fetch_list(session, code, page):
    return _extract_json(_get(session, LIST_URL.format(code=code, page=page)), "article_list")["re"] or []


def fetch_content(session, code, post_id):
    return _clean(_extract_json(_get(session, POST_URL.format(code=code, post_id=post_id)),
                                "post_article").get("post_content"))


def _upsert(db, code, p, score_fn):
    s, label, hits = score_fn(p["post_title"])
    row = (p["post_id"], code, p["post_title"], p["user_id"], p["user_nickname"],
           p["post_publish_time"], p["post_last_time"], p["post_click_count"],
           p["post_comment_count"], p["post_forward_count"], p["post_type"],
           p["post_top_status"], s, label, ",".join(hits), datetime.now().isoformat(timespec="seconds"))
    cur = db.execute("""INSERT OR IGNORE INTO posts (post_id, code, title, user_id, user_nickname,
        publish_time, last_time, clicks, comments, forwards, post_type, is_top,
        score, label, hits, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", row)
    if cur.rowcount:
        return True
    db.execute("UPDATE posts SET last_time=?, clicks=?, comments=?, forwards=?, fetched_at=? WHERE post_id=?",
               (p["post_last_time"], p["post_click_count"], p["post_comment_count"],
                p["post_forward_count"], row[-1], p["post_id"]))
    return False


def collect(db, code, score_fn, since_hours=24, max_pages=10, content_limit=0, use_proxy=False, log=print):
    """抓最近 since_hours 小时内有动态的帖子。content_limit>0 时再给点击最高的帖子补正文。"""
    session = make_session(use_proxy)
    cutoff = (datetime.now() - timedelta(hours=since_hours)).strftime("%Y-%m-%d %H:%M:%S")
    new = seen = 0
    for page in range(1, max_pages + 1):
        posts = fetch_list(session, code, page)
        if not posts:
            break
        stop = False
        for p in posts:
            stop = unchanged_post(db, p)
            new += _upsert(db, code, p, score_fn)
            seen += 1
            # 游标用于记录进度；下一轮仍从首页检查新动态，不跳过失败页之前的新帖。
            save_cursor(db, PLATFORM, code, {"page": page, "post_id": p["post_id"],
                                           "last_time": p["post_last_time"]})
            if stop:
                break
        db.commit()
        oldest = min((p["post_last_time"] for p in posts if not p["post_top_status"]), default=cutoff)
        log(f"第 {page} 页 {len(posts)} 条，最早动态 {oldest}")
        if stop or oldest < cutoff:
            break

    todo = db.execute("""SELECT post_id, title FROM posts WHERE code=? AND content IS NULL
        AND publish_time >= ? ORDER BY clicks DESC LIMIT ?""", (code, cutoff, content_limit)).fetchall()
    for post_id, title in todo:
        content = fetch_content(session, code, post_id)
        s, label, hits = score_fn(f"{title} {content}")
        db.execute("UPDATE posts SET content=?, score=?, label=?, hits=?, llm_label=NULL WHERE post_id=?",
                   (content, s, label, ",".join(hits), post_id))
        db.commit()
    log(f"本次处理 {seen} 条，新增 {new} 条，补正文 {len(todo)} 条")
    return new


def parse_comments(payload, post_id):
    """解析 fixture 约定的一级评论及 child_replys，拒绝无关响应。"""
    # 字段名是假设，待真实响应校准。仅接受 {"re": [...]}，不猜测其他接口。
    if not isinstance(payload, dict) or not isinstance(payload.get("re"), list):
        raise ValueError("评论响应必须包含 re 评论数组")
    out = []

    def parse(row, parent=None):
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str)
                for k in ("reply_text", "reply_time", "user_id", "user_nickname")):
            raise ValueError("评论字段不符")
        children = row.get("child_replys", [])
        if not isinstance(children, list):
            raise ValueError("child_replys 必须是数组")
        raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        reply_id = row.get("reply_id")
        if reply_id is not None and (isinstance(reply_id, bool) or not isinstance(reply_id, (str, int))):
            raise ValueError("reply_id 必须是字符串或整数")
        # 缺少原生 ID 时不用点赞数、昵称、子回复或列表位置，保证重复抓取稳定。
        identity = json.dumps([str(post_id), parent, row["user_id"], row["reply_time"],
                               row["reply_text"]], ensure_ascii=False)
        cid = (f"{post_id}:{reply_id}" if reply_id not in (None, "")
               else "sha256:" + hashlib.sha256(identity.encode()).hexdigest())
        likes = row.get("reply_like_count", 0)
        if isinstance(likes, bool) or not isinstance(likes, int) or likes < 0:
            raise ValueError("reply_like_count 必须是非负整数")
        out.append(dict(comment_id=cid, post_id=post_id, parent_comment_id=parent,
                        author_id=row["user_id"], author_nickname=row["user_nickname"],
                        content=_clean(row["reply_text"]), like_count=likes,
                        publish_time=row["reply_time"], raw_hash=hashlib.sha256(raw.encode()).hexdigest()))
        for child in children:
            parse(child, cid)

    for row in payload["re"]:
        parse(row)
    return out
