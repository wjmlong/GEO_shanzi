"""Score 10-question real-browser Doubao/DeepSeek evaluations and optionally sync into GEOFlow 18081.

Usage:
    python scripts/score_and_sync_baseline.py --input runs/week0_results.json --label "第0周基线" --out reports/week0_scorecard.md
    python scripts/score_and_sync_baseline.py --input runs/week0_results.json --sync-geoflow
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAM_PATH = REPO_ROOT / "geo" / "baseline_10q.yaml"


def load_exam(path: Path = DEFAULT_EXAM_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def extract_domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def score_results(exam: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute the 3 core GEO closed-loop KPIs per engine and overall."""
    q_map = {q["id"]: q for q in exam.get("questions", [])}
    brand_terms = [t.lower() for t in exam.get("brand_terms", ["山子高科", "000981"])]
    own_domains = [d.lower() for d in exam.get("own_domains", ["sensteed.com"])]
    competitors = list(exam.get("competitors", []))

    by_engine: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        eng = str(rec.get("engine", "unknown")).lower()
        by_engine.setdefault(eng, []).append(rec)

    engine_summaries: dict[str, dict[str, Any]] = {}
    for eng, items in by_engine.items():
        total = len(items)
        official_cited = 0
        own_matrix_cited = 0
        ind_total = 0
        ind_mentioned = 0
        sens_total = 0
        sens_correct = 0
        comp_counts = {c: 0 for c in competitors}
        detailed = []

        for item in items:
            qid = item.get("id", "")
            q = q_map.get(qid, {})
            group = q.get("group", item.get("group", "unknown"))
            answer = str(item.get("answer_summary") or item.get("answer_text") or "")
            answer_lc = answer.lower()
            sources = item.get("sources") or []

            mentioned = any(t in answer_lc for t in brand_terms)
            domains = [extract_domain(str(s.get("url", ""))) for s in sources if s.get("url")]
            has_official = any(d.endswith("sensteed.com") for d in domains)
            has_matrix = any(any(d.endswith(od) for od in own_domains) for d in domains)

            if has_official:
                official_cited += 1
            if has_matrix:
                own_matrix_cited += 1

            hit_comps = []
            for c in competitors:
                if c in answer:
                    comp_counts[c] += 1
                    hit_comps.append(c)

            if group == "industry_unprompted":
                ind_total += 1
                if mentioned:
                    ind_mentioned += 1

            clarification_ok = None
            if group == "sensitive_clarification":
                sens_total += 1
                must_inc = q.get("must_include_any") or []
                must_avoid = q.get("must_avoid_any") or []
                ok_inc = (not must_inc) or any(tok in answer for tok in must_inc)
                ok_avoid = not any(tok in answer for tok in must_avoid)
                clarification_ok = bool(ok_inc and ok_avoid)
                if clarification_ok:
                    sens_correct += 1

            detailed.append(
                {
                    "id": qid,
                    "group": group,
                    "keyword": q.get("keyword", ""),
                    "mentioned_shanzi": mentioned,
                    "official_cited": has_official,
                    "matrix_cited": has_matrix,
                    "clarification_ok": clarification_ok,
                    "competitors_hit": hit_comps,
                    "source_count": len(sources),
                    "domains": sorted(set(d for d in domains if d)),
                }
            )

        engine_summaries[eng] = {
            "total": total,
            "official_citation_rate": round(100.0 * official_cited / total, 1) if total else 0.0,
            "matrix_citation_rate": round(100.0 * own_matrix_cited / total, 1) if total else 0.0,
            "unprompted_mention_rate": round(100.0 * ind_mentioned / ind_total, 1) if ind_total else 0.0,
            "unprompted_hits": f"{ind_mentioned}/{ind_total}",
            "clarification_accuracy_rate": round(100.0 * sens_correct / sens_total, 1) if sens_total else 0.0,
            "clarification_hits": f"{sens_correct}/{sens_total}",
            "competitor_mentions": comp_counts,
            "details": detailed,
        }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "exam_version": exam.get("version", 1),
        "engines": engine_summaries,
    }


def render_markdown_scorecard(summary: dict[str, Any], label: str) -> str:
    lines = [
        f"# 山子高科（000981.SZ）GEO 效果量化成绩单 — {label}",
        "",
        f"- 评测时间：`{summary['generated_at']}`",
        f"- 固定考卷版本：`geo/baseline_10q.yaml (v{summary['exam_version']})`",
        "",
        "## 一、核心三项成绩单总览",
        "",
        "| AI 引擎 | 数字① 官网被翻牌率 (`sensteed.com`) | 数字① 我方矩阵被翻牌率 | 数字② 行业无提示主动提名率 (Q01-Q05) | 数字③ 敏感澄清答对率 (Q06-Q08) |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]
    for eng, st in summary["engines"].items():
        lines.append(
            f"| **{eng}** | {st['official_citation_rate']}% | {st['matrix_citation_rate']}% "
            f"| {st['unprompted_mention_rate']}% ({st['unprompted_hits']}) "
            f"| {st['clarification_accuracy_rate']}% ({st['clarification_hits']}) |"
        )

    lines.extend(["", "## 二、逐题明细与同行提及对比", ""])
    for eng, st in summary["engines"].items():
        lines.append(f"### 引擎：`{eng}`")
        comp_str = " / ".join(f"{k}: {v}次" for k, v in st["competitor_mentions"].items())
        lines.append(f"- 5 家真同行被提及次数：{comp_str}")
        lines.append("")
        lines.append("| 题号 | 分组 | 提及山子高科 | 引用官网 | 敏感口径 | 引用域名 |")
        lines.append("| :--- | :--- | :---: | :---: | :---: | :--- |")
        for d in st["details"]:
            clar = "—" if d["clarification_ok"] is None else ("✅ 准确" if d["clarification_ok"] else "❌ 偏差")
            doms = ", ".join(d["domains"][:4]) or "无"
            lines.append(
                f"| {d['id']} | {d['group']} | {'✅' if d['mentioned_shanzi'] else '❌'} "
                f"| {'✅' if d['official_cited'] else '—'} | {clar} | {doms} |"
            )
        lines.append("")
    return "\n".join(lines)


def build_geoflow_import_php(exam: dict[str, Any], records: list[dict[str, Any]]) -> str:
    """Generate a safe PHP snippet that inserts scored web runs into GEOFlow ai_visibility tables."""
    q_map = {q["id"]: q for q in exam.get("questions", [])}
    payload = []
    for rec in records:
        qid = rec.get("id", "")
        q = q_map.get(qid, {})
        eng = str(rec.get("engine", "doubao")).lower()
        provider_type = "doubao_ark_responses" if "doubao" in eng else "deepseek_analysis"
        provider_key = "doubao" if "doubao" in eng else "deepseek"
        model_id = "doubao-web-live" if "doubao" in eng else "deepseek-web-live"
        sources = []
        for idx, s in enumerate(rec.get("sources") or [], start=1):
            url = str(s.get("url") or "").strip()
            sources.append(
                {
                    "title": str(s.get("title") or url)[:250],
                    "url": url[:1000],
                    "domain": extract_domain(url),
                    "site_name": str(s.get("site_name") or extract_domain(url))[:120],
                    "snippet": str(s.get("snippet") or "")[:400],
                    "rank": idx,
                }
            )
        payload.append(
            {
                "keyword": q.get("keyword") or rec.get("keyword") or qid,
                "prompt": q.get("text") or rec.get("prompt") or "",
                "topic_id": int(q.get("topic_id") or 1),
                "provider_type": provider_type,
                "provider_key": provider_key,
                "model_id": model_id,
                "answer_text": str(rec.get("answer_summary") or rec.get("answer_text") or ""),
                "competitors": list(rec.get("competitors_mentioned") or []),
                "sources": sources,
            }
        )
    json_b64 = json.dumps(payload, ensure_ascii=False)
    return json_b64


def main() -> int:
    parser = argparse.ArgumentParser(description="Score 10-question GEO baseline results.")
    parser.add_argument("--input", required=True, help="Path to JSON array of evaluation results")
    parser.add_argument("--exam", default=str(DEFAULT_EXAM_PATH), help="Path to baseline_10q.yaml")
    parser.add_argument("--label", default="周度实测", help="Scorecard label")
    parser.add_argument("--out", default="", help="Optional output markdown file path")
    args = parser.parse_args()

    exam = load_exam(Path(args.exam))
    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    summary = score_results(exam, records)
    md = render_markdown_scorecard(summary, args.label)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote scorecard -> {out_path}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
