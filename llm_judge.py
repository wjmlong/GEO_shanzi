"""用大模型给股吧帖子做情绪复判，重点识别反讽、黑话。结果写回 guba.db 的 llm_* 列。

依赖：pip install anthropic
凭据和网关沿用环境变量 ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL（请求头 anthropic-version 固定为 2023-06-01）；
模型用 JUDGE_MODEL，未设置时用 ANTHROPIC_MODEL。
"""
import json
import os
from datetime import datetime

import anthropic

SYSTEM = """你是A股股吧舆情分析员。逐条判断帖子作者对这只股票（或公司）的真实情绪。
股吧常见反讽和黑话，要按真实意图判断，不要看字面：
- “大盘涨了1%，你涨了2分钱” 是嘲讽走势弱，负面
- “垃圾桶”“韭菜收割机”“熟悉的配方” 一般是负面
- “稳了”“格局打开” 可能是真看多，也可能是反讽，结合上下文判断
- 纯观望、问问题、闲聊，判中性
label 只能是 正面 / 中性 / 负面；score 取 -1 到 1，负数偏空，正数偏多；
sarcasm 表示是否用了反讽；reason 用不超过 20 个字说明依据。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer"},
                    "label": {"type": "string", "enum": ["正面", "中性", "负面"]},
                    "score": {"type": "number"},
                    "sarcasm": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["post_id", "label", "score", "sarcasm", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _text(resp):
    return next((b.text for b in resp.content if b.type == "text"), "")


def judge_batch(client, model, posts):
    """posts: [(post_id, title, content)]。返回 {post_id: dict}。"""
    payload = [{"post_id": pid, "text": f"{title} {content or ''}".strip()[:500]}
               for pid, title, content in posts]
    kwargs = dict(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    try:
        resp = client.messages.create(
            **kwargs, output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}})
        data = json.loads(_text(resp))
    except anthropic.BadRequestError:
        # 部分中转网关不支持 output_config，退回到提示词约束 JSON
        kwargs["system"] = SYSTEM + '\n只输出 JSON：{"results": [{"post_id", "label", "score", "sarcasm", "reason"}]}，不要别的文字。'
        text = _text(client.messages.create(**kwargs))
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])

    sent = {p["post_id"] for p in payload}
    out = {}
    for r in data.get("results", []):
        if r.get("post_id") in sent and r.get("label") in ("正面", "中性", "负面"):
            r["score"] = max(-1.0, min(1.0, float(r.get("score", 0))))
            out[r["post_id"]] = r
    return out


def judge_pending(db, code, limit=300, batch_size=30, model=None, client=None, log=print):
    """给还没复判过的帖子做复判，返回成功写入的条数。"""
    model = model or os.environ.get("JUDGE_MODEL") or os.environ.get("ANTHROPIC_MODEL")
    if not model:
        raise SystemExit("请设置 JUDGE_MODEL 或 ANTHROPIC_MODEL")
    # 当前网关不认新版 SDK 默认的 anthropic-version，固定成 2023-06-01
    client = client or anthropic.Anthropic(default_headers={"anthropic-version": "2023-06-01"})
    rows = db.execute("""SELECT post_id, title, content FROM posts
        WHERE code=? AND llm_label IS NULL ORDER BY publish_time DESC LIMIT ?""", (code, limit)).fetchall()
    done = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            results = judge_batch(client, model, batch)
        except (anthropic.APIStatusError, anthropic.APIConnectionError, ValueError) as e:
            log(f"第 {i // batch_size + 1} 批复判失败，跳过：{e}")
            continue
        now = datetime.now().isoformat(timespec="seconds")
        for pid, r in results.items():
            db.execute("""UPDATE posts SET llm_label=?, llm_score=?, llm_sarcasm=?, llm_reason=?,
                llm_model=?, llm_at=? WHERE post_id=?""",
                       (r["label"], r["score"], int(bool(r["sarcasm"])), r["reason"][:60], model, now, pid))
        db.commit()
        done += len(results)
        log(f"第 {i // batch_size + 1} 批：{len(batch)} 条，成功 {len(results)} 条")
    return done
