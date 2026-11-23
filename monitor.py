"""股吧舆情监控入口。

用法：
  python3 monitor.py collect               # 抓一次
  python3 monitor.py status                # 查看平台状态和最近采集记录
  python3 monitor.py report                # 输出最近 24 小时报告
  python3 monitor.py judge                 # 用大模型复判还没复判过的帖子（需 pip install anthropic）
  python3 monitor.py run --interval 30     # 每 30 分钟抓一次，报告存到 reports/；加 --llm 每轮顺带复判
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from collector import PLATFORM, Blocked, collect, connect
from store import finish_run, is_blocked, record_failure, record_success, start_run
from report import build_report
from sentiment import score

HERE = Path(__file__).parent


def run_once(db, args):
    now = datetime.now()
    if is_blocked(db, PLATFORM, now):
        until = db.execute("SELECT blocked_until FROM platform_state WHERE platform=?",
                           (PLATFORM,)).fetchone()[0]
        remaining = datetime.fromisoformat(until) - now
        print(f"{PLATFORM} 退避中，跳过本轮，剩余 {remaining.total_seconds() / 60:.1f} 分钟")
        return False
    run_id = start_run(db, PLATFORM)
    before = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    status, error = "success", None
    try:
        collect(db, args.code, score, since_hours=args.hours, max_pages=args.pages,
                content_limit=args.content, use_proxy=args.proxy)
    except Exception as exc:
        status = "blocked" if isinstance(exc, Blocked) else "error"
        error = str(exc) or type(exc).__name__
        until = record_failure(db, PLATFORM, exc)
        print(f"{PLATFORM} 采集失败：{error}；退避至 {until:%Y-%m-%d %H:%M:%S}", file=sys.stderr)
    else:
        record_success(db, PLATFORM)
    finally:
        added = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0] - before
        finish_run(db, run_id, status, new_posts=added, error=error)
    return status == "success"


def print_status(db):
    rows = db.execute("""SELECT platform, last_ok_at, blocked_until, consecutive_failures,
        last_error FROM platform_state ORDER BY platform""").fetchall()
    if not rows:
        print("暂无平台状态")
    for platform, last_ok, until, failures, error in rows:
        print(f"{platform}: last_ok_at={last_ok or '-'} blocked_until={until or '-'} "
              f"失败次数={failures} last_error={error or '-'}")
    print("最近 5 次 crawl_runs：")
    for row in db.execute("""SELECT id, platform, started_at, finished_at, status,
            new_posts, new_comments, error FROM crawl_runs ORDER BY id DESC LIMIT 5"""):
        print(f"#{row[0]} {row[1]} {row[2]} -> {row[3] or '-'} {row[4]} "
              f"新增帖子={row[5]} 新增评论={row[6]} 错误={row[7] or '-'}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "geo":
        from geo.cli import main as geo_main
        return geo_main(sys.argv[2:])
    ap = argparse.ArgumentParser(description="东方财富股吧舆情监控")
    ap.add_argument("cmd", choices=["collect", "report", "judge", "run", "status"])
    ap.add_argument("--code", default="000981", help="股票代码，默认 000981 山子高科")
    ap.add_argument("--hours", type=int, default=24, help="统计/抓取时间窗口（小时）")
    ap.add_argument("--pages", type=int, default=10, help="每轮最多翻几页列表（每页 80 条）")
    ap.add_argument("--content", type=int, default=0, help="每轮给多少条热帖补正文，默认 0")
    ap.add_argument("--interval", type=int, default=30, help="run 模式的间隔（分钟）")
    ap.add_argument("--db", default=str(HERE / "guba.db"))
    ap.add_argument("--proxy", action="store_true", help="使用系统 http_proxy（默认直连）")
    ap.add_argument("--llm", action="store_true", help="run 模式下每轮抓完后用大模型复判新帖")
    args = ap.parse_args()

    db = connect(args.db)
    if args.cmd == "collect":
        run_once(db, args)
    elif args.cmd == "status":
        print_status(db)
    elif args.cmd == "report":
        print(build_report(db, args.code, args.hours)[0])
    elif args.cmd == "judge":
        from llm_judge import judge_pending  # 只有这里需要 anthropic 包
        print(f"复判完成 {judge_pending(db, args.code)} 条")
    else:
        (HERE / "reports").mkdir(exist_ok=True)
        while True:
            ok = run_once(db, args)
            if args.llm:
                from llm_judge import judge_pending
                judge_pending(db, args.code)
            text, alerts = build_report(db, args.code, args.hours)
            (HERE / "reports" / f"{args.code}_{datetime.now():%Y%m%d_%H%M}.md").write_text(text, encoding="utf-8")
            print(f"[{datetime.now():%H:%M}] 本轮完成，告警 {len(alerts)} 条")
            for a in alerts:
                print(f"  ⚠ {a}")
            time.sleep(args.interval * 60)  # 平台退避由持久化 blocked_until 控制


if __name__ == "__main__":
    main()
