"""从本地 GEO 样本生成 Markdown 报告。"""
import json
from collections import Counter


def _groups(db, run_id):
    rows = db.execute("""SELECT engine, question_group,
        SUM(CASE WHEN error IS NULL OR error='' THEN 1 ELSE 0 END),
        SUM(CASE WHEN error IS NULL OR error='' THEN 0 ELSE 1 END),
        SUM(CASE WHEN (error IS NULL OR error='') AND mentioned=1 THEN 1 ELSE 0 END),
        AVG(CASE WHEN (error IS NULL OR error='') AND mentioned=1 THEN first_pos END),
        SUM(CASE WHEN (error IS NULL OR error='') AND label='正面' THEN 1 ELSE 0 END),
        SUM(CASE WHEN (error IS NULL OR error='') AND label='中性' THEN 1 ELSE 0 END),
        SUM(CASE WHEN (error IS NULL OR error='') AND label='负面' THEN 1 ELSE 0 END)
        FROM geo_samples WHERE run_id=? GROUP BY engine, question_group""", (run_id,))
    return {(row[0], row[1]): tuple(row[2:]) for row in rows}


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def build_geo_report(db, run_id=None):
    if run_id is None:
        row = db.execute("SELECT MAX(id) FROM geo_runs").fetchone()
        run_id = row[0]
    if run_id is None or not db.execute("SELECT 1 FROM geo_runs WHERE id=?", (run_id,)).fetchone():
        return "# GEO 报告\n\n暂无运行记录。\n"
    previous = db.execute("SELECT MAX(id) FROM geo_runs WHERE id<?", (run_id,)).fetchone()[0]
    current = _groups(db, run_id)
    prior = _groups(db, previous) if previous is not None else {}
    keys = set(current) | set(prior)
    for engine, _ in list(keys):
        keys.update((engine, group) for group in ("brand", "category", "holdout"))
    lines = [f"# GEO 报告：run {run_id}", "",
             "| engine | question_group | 有效样本数 | error 样本数 | 提及率 | 平均首次提及偏移 | 正面 | 中性 | 负面 |" +
             (f" 较上一 run {previous} 差值（百分点） |" if previous is not None else ""),
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |" +
             (" ---: |" if previous is not None else "")]
    order = {"brand": 0, "category": 1, "holdout": 2}
    for key in sorted(keys, key=lambda k: (str(k[0]), order.get(k[1], 3), str(k[1]))):
        valid, errors, mentions, offset, positive, neutral, negative = current.get(key, (0, 0, 0, None, 0, 0, 0))
        rate = mentions / valid if valid else None
        cells = [*key, valid, errors, f"{rate:.2%}" if rate is not None else "无有效样本",
                 f"{offset:.2f}" if offset is not None else "—", positive, neutral, negative]
        if previous is not None:
            old = prior.get(key)
            cells.append(f"{100 * (rate - old[2] / old[0]):+.2f}" if rate is not None and old and old[0]
                         else "无法比较（无有效样本）")
        lines.append("| " + " | ".join(map(_cell, cells)) + " |")
    domains = Counter()
    for (raw,) in db.execute("""SELECT domains_json FROM geo_samples
            WHERE run_id=? AND (error IS NULL OR error='')""", (run_id,)):
        # 每个有效回答对同一域名计一次引用。
        domains.update(dict.fromkeys(json.loads(raw or "[]"), 1))
    lines.extend(["", "## 被引用域名 Top10", "", "| 域名 | 有效回答引用数 |", "| --- | ---: |"])
    lines.extend(f"| {_cell(domain)} | {count} |" for domain, count in domains.most_common(10))
    if not domains:
        lines.append("| 无引用域名 | 0 |")
    return "\n".join(lines) + "\n"


# CLI 使用配置隔离报告；保留 build_geo_report 兼容已有核心调用方。
GROUPS = ("brand", "category", "holdout")


def summarize(db, run_id):
    from collections import defaultdict
    buckets = defaultdict(list)
    cur = db.execute("SELECT * FROM geo_samples WHERE run_id=?", (run_id,))
    names = [c[0] for c in cur.description]
    for values in cur:
        row = dict(zip(names, values))
        key = tuple(row[k] for k in ("engine", "model", "web_search", "temperature", "question_group"))
        buckets[key].append(row)
    result = {}
    for key, rows in buckets.items():
        valid = [r for r in rows if not r["error"]]
        positions = [r["first_pos"] for r in valid if r["mentioned"] and r["first_pos"] is not None]
        domains = Counter()
        for row in valid:
            domains.update(json.loads(row["domains_json"] or '{}'))
        result[key] = dict(valid=len(valid), errors=len(rows)-len(valid),
                           mentioned=sum(bool(r["mentioned"]) for r in valid),
                           rate=sum(bool(r["mentioned"]) for r in valid)/len(valid) if valid else None,
                           position=sum(positions)/len(positions) if positions else None,
                           labels=Counter(r["label"] for r in valid), domains=domains)
    return result


def build_report(db, run_id=None):
    run = db.execute("SELECT id, question_version, started_at, finished_at, note FROM geo_runs " +
                     ("WHERE id=?" if run_id is not None else "ORDER BY id DESC LIMIT 1"),
                     (run_id,) if run_id is not None else ()).fetchone()
    if run is None:
        return "暂无 GEO 运行记录。"
    run_id, version, started, finished, note = run
    previous = db.execute("SELECT id, question_version FROM geo_runs WHERE id<? ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
    current = summarize(db, run_id)
    old = summarize(db, previous[0]) if previous else {}
    lines = [f"# GEO run {run_id}", f"题库版本：{version}；开始：{started}；结束：{finished or '未完成'}",
             f"记录：{note or '-'}", f"上一个 run：{previous[0] if previous else '无'}",
             "API 回答 ≠ App 联网搜索结果；本报告仅统计 API。error 不计入分母。",
             "首次位置为从 0 开始的字符偏移，仅对命中样本求平均；域名按文本出现次数统计。"]
    for group in GROUPS:
        lines += ["", f"## {group}", "",
                  "| 引擎 / 模型 / 联网 / 温度 | 有效 | error | 提及数 | 提及率 | 平均首次位置 | Δ提及率 | Δ位置 |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        keys = sorted((k for k in current if k[-1] == group), key=str)
        if not keys:
            lines.append("本组无样本（未选择、缺少配置或平台退避）。")
        for key in keys:
            row, before = current[key], old.get(key)
            comparable = before is not None and previous[1] == version
            rate = f'{row["rate"]:.1%}' if row["rate"] is not None else "N/A"
            pos = f'{row["position"]:.1f}' if row["position"] is not None else "N/A"
            dr = (f'{(row["rate"]-before["rate"])*100:+.1f} pp' if comparable and
                  row["rate"] is not None and before["rate"] is not None else "N/A")
            dp = (f'{row["position"]-before["position"]:+.1f}' if comparable and
                  row["position"] is not None and before["position"] is not None else "N/A")
            title = _cell(" / ".join(str(v) for v in key[:-1]))
            lines.append(f'| {title} | {row["valid"]} | {row["errors"]} | {row["mentioned"]} | {rate} | {pos} | {dr} | {dp} |')
        for key in keys:
            row, before = current[key], old.get(key)
            comparable = before is not None and previous[1] == version
            lines += ["", f"### {' / '.join(map(str, key[:-1]))}", "",
                      "情感分布：" + "、".join(f"{label}={row['labels'][label]}" for label in ("正面", "中性", "负面")),
                      "域名 Top10：" + ("、".join(f"{d}={n}" for d, n in row["domains"].most_common(10)) or "无")]
            if comparable:
                lines.append(f"较上轮：有效 {row['valid']-before['valid']:+d}，error {row['errors']-before['errors']:+d}；情感计数差：" +
                             "、".join(f"{s}={row['labels'][s]-before['labels'][s]:+d}" for s in ("正面", "中性", "负面")))
                lines.append("当前 Top10 域名计数差：" + ("、".join(f"{d}={n-before['domains'][d]:+d}" for d, n in row["domains"].most_common(10)) or "无"))
    lines += ["", "差值仅比较上一 run 中相同题库版本、引擎、模型、联网模式与温度；否则 N/A。",
              "题目子集、重复次数或配置变化仍会影响可比性；编辑题库请递增 version。"]
    return "\n".join(lines)
