"""GEO 独立迁移，兼容既有表；每个 HTTP 尝试单独留档。"""
import json
from datetime import datetime

import store


def migrate_geo(db):
    db.execute("""CREATE TABLE IF NOT EXISTS geo_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT, question_version TEXT, note TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS geo_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, engine TEXT, model TEXT, web_search TEXT,
        temperature REAL, question_id TEXT, question_group TEXT, repeat_idx INTEGER,
        asked_at TEXT, latency_ms INTEGER, answer_text TEXT, raw_json TEXT,
        tokens_in INTEGER, tokens_out INTEGER, error TEXT, mentioned INTEGER,
        first_pos INTEGER, mention_count INTEGER, competitors_json TEXT, domains_json TEXT,
        score REAL, label TEXT)""")
    db.commit()


def migrate(db):
    store.migrate(db)
    migrate_geo(db)
    columns = {row[1] for row in db.execute("PRAGMA table_info(geo_samples)")}
    if "analysis_json" not in columns:
        db.execute("ALTER TABLE geo_samples ADD COLUMN analysis_json TEXT")
    db.execute("""CREATE TABLE IF NOT EXISTS geo_attempts (
        id INTEGER PRIMARY KEY, sample_id INTEGER, attempt_idx INTEGER, asked_at TEXT,
        latency_ms INTEGER, status INTEGER, raw_json TEXT, error TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_geo_run ON geo_samples(run_id)")
    db.commit()


def start_run(db, question_version, note=None):
    cur = db.execute("INSERT INTO geo_runs(started_at, question_version, note) VALUES (?,?,?)",
                     (datetime.now().isoformat(), str(question_version), note))
    db.commit()
    return cur.lastrowid


def finish_run(db, run_id):
    db.execute("UPDATE geo_runs SET finished_at=? WHERE id=?", (datetime.now().isoformat(), run_id))
    db.commit()


def insert_sample(db, run_id, **fields):
    """插入一条样本并提交；JSON 字段接受 JSON 字符串或 Python 对象。"""
    allowed = set("engine model web_search temperature question_id question_group repeat_idx "
                  "asked_at latency_ms answer_text raw_json tokens_in tokens_out error mentioned "
                  "first_pos mention_count competitors_json domains_json score label".split())
    unknown = fields.keys() - allowed
    if unknown:
        raise ValueError("未知样本字段: " + ", ".join(sorted(unknown)))
    row = dict(run_id=run_id, **fields)
    for key in ("raw_json", "competitors_json", "domains_json"):
        if key in row and row[key] is not None and not isinstance(row[key], str):
            row[key] = json.dumps(row[key], ensure_ascii=False)
    cur = db.execute(f"INSERT INTO geo_samples ({','.join(row)}) "
                     f"VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    db.commit()
    return cur.lastrowid


def save_sample(db, run_id, question, repeat_idx, sample, analysis):
    row = {k: v for k, v in sample.items() if k != "attempts"}
    row.update(run_id=run_id, question_id=question["id"], question_group=question["group"], repeat_idx=repeat_idx)
    row["raw_json"] = json.dumps(row["raw_json"], ensure_ascii=False)
    row.update({k: analysis.get(k) for k in ("mentioned", "first_pos", "mention_count", "score", "label")})
    for key in ("competitors", "domains"):
        row[key + "_json"] = json.dumps(analysis.get(key, {}), ensure_ascii=False)
    row["analysis_json"] = json.dumps(analysis, ensure_ascii=False)
    cur = db.execute(f"INSERT INTO geo_samples ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    for idx, attempt in enumerate(sample.get("attempts", []), 1):
        db.execute("""INSERT INTO geo_attempts(sample_id, attempt_idx, asked_at, latency_ms, status, raw_json, error)
            VALUES (?,?,?,?,?,?,?)""", (cur.lastrowid, idx, attempt["asked_at"], attempt["latency_ms"],
            attempt["status"], json.dumps(attempt["raw_json"], ensure_ascii=False), attempt["error"]))
    db.commit()
