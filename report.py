"""舆情统计与告警：按时间窗口汇总情绪，并和上一个同长度窗口对比。"""
from collections import Counter
from datetime import datetime, timedelta

RISK_WORDS = ("立案", "退市", "爆雷", "造假", "处罚", "冻结", "诉讼", "违规",
              "质押", "强平", "减持", "停牌", "st")


def window_stats(db, code, start, end):
    # 有大模型复判结果时用复判标签，否则用词典标签
    rows = db.execute("""SELECT post_id, title, content, clicks, comments, score,
        COALESCE(llm_label, label), hits, llm_label IS NOT NULL, COALESCE(llm_sarcasm, 0)
        FROM posts WHERE code=? AND publish_time >= ? AND publish_time < ?""",
                      (code, start, end)).fetchall()
    labels = Counter(r[6] for r in rows)
    total = len(rows)
    risks = Counter()
    for r in rows:
        text = f"{r[1]} {r[2] or ''}".lower()
        risks.update(w for w in RISK_WORDS if w in text)
    words = Counter(w for r in rows for w in (r[7] or "").split(",") if w)
    return {
        "total": total,
        "labels": labels,
        "neg_ratio": labels["负面"] / total if total else 0.0,
        "avg_score": sum(r[5] for r in rows) / total if total else 0.0,
        "hot": sorted(rows, key=lambda r: r[3], reverse=True)[:5],
        "most_negative": sorted(rows, key=lambda r: r[5])[:5],
        "risks": risks,
        "words": words.most_common(10),
        "llm_judged": sum(r[8] for r in rows),
        "sarcasm": sum(r[9] for r in rows),
    }


def build_report(db, code, hours=24, neg_jump=0.10, volume_ratio=2.0):
    """返回 (markdown 文本, 告警列表)。"""
    fmt = "%Y-%m-%d %H:%M:%S"
    now = datetime.now()
    cur_start, prev_start = now - timedelta(hours=hours), now - timedelta(hours=2 * hours)
    cur = window_stats(db, code, cur_start.strftime(fmt), now.strftime(fmt))
    prev = window_stats(db, code, prev_start.strftime(fmt), cur_start.strftime(fmt))

    alerts = []
    if prev["total"] >= 20 and cur["neg_ratio"] - prev["neg_ratio"] >= neg_jump:
        alerts.append(f"负面占比从 {prev['neg_ratio']:.0%} 升到 {cur['neg_ratio']:.0%}")
    if prev["total"] >= 20 and cur["total"] >= volume_ratio * prev["total"]:
        alerts.append(f"发帖量从 {prev['total']} 增加到 {cur['total']}")
    for w, n in cur["risks"].items():
        if n >= 3:
            alerts.append(f"风险词“{w}”出现 {n} 次")

    lab = cur["labels"]
    change = f"（上一周期 {prev['total']}）" if prev["total"] else "（上一周期无数据）"
    lines = [
        f"## {code} 股吧舆情 最近 {hours} 小时",
        f"统计时间：{now.strftime('%Y-%m-%d %H:%M')}",
        f"- 发帖数：{cur['total']}{change}",
        f"- 正面 {lab['正面']} / 中性 {lab['中性']} / 负面 {lab['负面']}，"
        f"负面占比 {cur['neg_ratio']:.0%}，平均分 {cur['avg_score']:.2f}",
        f"- 情绪判定：大模型复判 {cur['llm_judged']} 条（其中反讽 {cur['sarcasm']} 条），其余用词典",
        f"- 高频情绪词：{'、'.join(f'{w}({n})' for w, n in cur['words']) or '无'}",
        f"- 风险词：{'、'.join(f'{w}({n})' for w, n in cur['risks'].most_common()) or '无'}",
        "", "**告警**", *([f"- ⚠ {a}" for a in alerts] or ["- 无"]),
        "", "**阅读量最高**",
        *[f"- [{r[6]}] {r[1][:40]}（阅读 {r[3]}，评论 {r[4]}）" for r in cur["hot"]],
        "", "**最负面**",
        *[f"- ({r[5]}) {r[1][:40]}" for r in cur["most_negative"] if r[5] < 0],
    ]
    return "\n".join(lines), alerts
