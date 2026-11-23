"""SQLite 数据层：兼容 posts，保存评论、平台状态与采集记录。"""
import json
from datetime import datetime, timedelta

LLM_COLUMNS = {"llm_label": "TEXT", "llm_score": "REAL", "llm_sarcasm": "INTEGER",
               "llm_reason": "TEXT", "llm_model": "TEXT", "llm_at": "TEXT"}


def migrate(db):
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS posts (
        post_id INTEGER PRIMARY KEY, code TEXT, title TEXT, content TEXT,
        user_id TEXT, user_nickname TEXT, publish_time TEXT, last_time TEXT,
        clicks INTEGER, comments INTEGER, forwards INTEGER,
        post_type INTEGER, is_top INTEGER,
        score REAL, label TEXT, hits TEXT, fetched_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_posts_time ON posts(code, publish_time)")
    have = {r[1] for r in db.execute("PRAGMA table_info(posts)")}
    for col, typ in {**LLM_COLUMNS, "comments_fetched_count": "INTEGER NOT NULL DEFAULT 0"}.items():
        if col not in have:
            db.execute(f"ALTER TABLE posts ADD COLUMN {col} {typ}")
    db.execute("""CREATE TABLE IF NOT EXISTS comments (
        platform TEXT, comment_id TEXT, post_id INTEGER, parent_comment_id TEXT,
        author_id TEXT, author_nickname TEXT, content TEXT, like_count INTEGER,
        publish_time TEXT, fetched_at TEXT, first_seen_at TEXT, raw_hash TEXT,
        score REAL, label TEXT, hits TEXT, PRIMARY KEY(platform, comment_id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS platform_state (
        platform TEXT PRIMARY KEY, last_ok_at TEXT, last_error TEXT, blocked_until TEXT,
        consecutive_failures INTEGER NOT NULL DEFAULT 0, cursor_json TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS crawl_runs (
        id INTEGER PRIMARY KEY, platform TEXT, started_at TEXT, finished_at TEXT,
        status TEXT, new_posts INTEGER DEFAULT 0, new_comments INTEGER DEFAULT 0, error TEXT)""")
    db.commit()


def upsert_comment(db, platform, comment, score_fn, now=None):
    """返回是否新增；保留首次发现时间。提交由调用方负责。"""
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    s, label, hits = score_fn(comment["content"])
    exists = db.execute("SELECT 1 FROM comments WHERE platform=? AND comment_id=?",
                        (platform, comment["comment_id"])).fetchone()
    db.execute("""INSERT INTO comments (platform, comment_id, post_id, parent_comment_id,
        author_id, author_nickname, content, like_count, publish_time, fetched_at,
        first_seen_at, raw_hash, score, label, hits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(platform, comment_id) DO UPDATE SET
        post_id=excluded.post_id, parent_comment_id=excluded.parent_comment_id,
        author_id=excluded.author_id, author_nickname=excluded.author_nickname,
        content=excluded.content, like_count=excluded.like_count,
        publish_time=excluded.publish_time, fetched_at=excluded.fetched_at,
        raw_hash=excluded.raw_hash, score=excluded.score, label=excluded.label, hits=excluded.hits""",
               (platform, comment["comment_id"], comment["post_id"], comment.get("parent_comment_id"),
                comment.get("author_id"), comment.get("author_nickname"), comment["content"],
                comment.get("like_count", 0), comment.get("publish_time"), stamp, stamp,
                comment.get("raw_hash"), s, label, ",".join(hits)))
    return exists is None


def pending_comments(db, code):
    """未完整抓取的评论数仍保持待抓状态；完整抓完后才能更新 fetched_count。"""
    return db.execute("""SELECT post_id, comments FROM posts
        WHERE code=? AND comments > comments_fetched_count""", (code,)).fetchall()


def unchanged_post(db, post):
    row = db.execute("SELECT last_time FROM posts WHERE post_id=?", (post["post_id"],)).fetchone()
    return not post["post_top_status"] and row is not None and row[0] == post["post_last_time"]


def save_cursor(db, platform, code, cursor):
    row = db.execute("SELECT cursor_json FROM platform_state WHERE platform=?", (platform,)).fetchone()
    cursors = json.loads(row[0]) if row and row[0] else {}
    cursors[code] = cursor
    db.execute("""INSERT INTO platform_state(platform, cursor_json) VALUES (?,?)
        ON CONFLICT(platform) DO UPDATE SET cursor_json=excluded.cursor_json""",
               (platform, json.dumps(cursors, ensure_ascii=False)))


def record_success(db, platform, now=None):
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    db.execute("""INSERT INTO platform_state(platform, last_ok_at) VALUES (?,?)
        ON CONFLICT(platform) DO UPDATE SET last_ok_at=excluded.last_ok_at,
        last_error=NULL, blocked_until=NULL, consecutive_failures=0""", (platform, stamp))
    db.commit()


def record_failure(db, platform, error, now=None):
    """失败从 30 分钟起退避，最大 12 小时；验证拦截也使用此规则。"""
    now = now or datetime.now()
    row = db.execute("SELECT consecutive_failures FROM platform_state WHERE platform=?", (platform,)).fetchone()
    failures = (row[0] if row else 0) + 1
    until = now + timedelta(minutes=min(30 * 2 ** min(failures - 1, 5), 720))
    db.execute("""INSERT INTO platform_state(platform, last_error, blocked_until, consecutive_failures)
        VALUES (?,?,?,?) ON CONFLICT(platform) DO UPDATE SET last_error=excluded.last_error,
        blocked_until=excluded.blocked_until, consecutive_failures=excluded.consecutive_failures""",
               (platform, str(error) or type(error).__name__, until.isoformat(timespec="seconds"), failures))
    db.commit()
    return until


def is_blocked(db, platform, now=None):
    row = db.execute("SELECT blocked_until FROM platform_state WHERE platform=?", (platform,)).fetchone()
    return bool(row and row[0] and datetime.fromisoformat(row[0]) > (now or datetime.now()))


def start_run(db, platform):
    cur = db.execute("INSERT INTO crawl_runs(platform, started_at, status) VALUES (?,?,?)",
                     (platform, datetime.now().isoformat(timespec="seconds"), "running"))
    db.commit()
    return cur.lastrowid


def finish_run(db, run_id, status, new_posts=0, new_comments=0, error=None):
    db.execute("""UPDATE crawl_runs SET finished_at=?, status=?, new_posts=?, new_comments=?, error=?
        WHERE id=?""", (datetime.now().isoformat(timespec="seconds"), status,
                        new_posts, new_comments, error, run_id))
    db.commit()
