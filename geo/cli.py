"""GEO 命令行；dry-run 不打开数据库、不请求接口。"""
import argparse
import json
import math
import sqlite3
import time
from pathlib import Path

import yaml

import store
from geo import store_geo
from geo.analyze import analyze
from geo.engines import DeepSeekEngine, DoubaoEngine
from geo.report import GROUPS, build_report

HERE = Path(__file__).parent
ENGINES = {"deepseek": DeepSeekEngine, "doubao": DoubaoEngine}


def read_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def selection(value, allowed):
    selected = list(dict.fromkeys(v.strip() for v in value.split(",")))
    if not selected or any(v not in allowed for v in selected):
        raise ValueError("无效选项：" + value)
    return selected


def run_sampling(args, db=None, log=print):
    config = read_yaml(args.config)
    bank = read_yaml(args.questions)
    brand = read_yaml(args.brand)
    groups = selection(args.groups, GROUPS)
    names = selection(args.engines, ENGINES)
    repeat = args.repeat if args.repeat is not None else config.get("repeat", 3)
    interval = config.get("interval", 1)
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 1 or interval < 0:
        raise ValueError("repeat 必须为正整数，interval 必须非负")
    if "version" not in bank:
        raise ValueError("题库缺少 version")
    ids = set()
    for q in bank["questions"]:
        if not isinstance(q.get("id"), str) or q["id"] in ids or q.get("group") not in GROUPS or q.get("intent") not in ("buyer", "educate", "probe") or not isinstance(q.get("text"), str) or not q["text"].strip():
            raise ValueError("题目字段无效或 id 重复")
        ids.add(q["id"])
    questions = [q for q in bank["questions"] if q["group"] in groups]
    engines, skipped = [], []
    for name in names:
        settings = {k: config[k] for k in ("temperature", "interval", "timeout") if k in config}
        settings.update(config.get("engines", {}).get(name, {}))
        engine = ENGINES[name](settings)
        reason = engine.unavailable()
        if reason:
            message = f"跳过 {name}：{reason}"
            log(message)
            skipped.append(message)
        else:
            engines.append(engine)
    count = len(questions)*repeat*len(engines)
    if args.dry_run:
        estimated_in = sum(math.ceil(len(q["text"])*1.5)+16 for q in questions)*repeat*len(engines)
        estimated_out = count*config.get("estimated_output_tokens", 600)
        log(f"计划调用数：{count}；预估 token：输入 {estimated_in} + 输出 {estimated_out} = {estimated_in+estimated_out}（粗估，不含重试；最多 {count*4} 次 HTTP 请求；未查询平台退避）")
        return None
    if not engines or not questions:
        log("没有可执行的采样调用")
        return None
    owned = db is None
    if owned:
        db = sqlite3.connect(args.db)
    try:
        store_geo.migrate(db)
        active = []
        for engine in engines:
            if store.is_blocked(db, "geo:" + engine.name):
                message = f"跳过 {engine.name}：平台退避中"
                log(message)
                skipped.append(message)
            else:
                active.append(engine)
        note = json.dumps(dict(groups=groups, repeat=repeat, skipped=skipped,
                               questions=questions, brand=brand, config=config), ensure_ascii=False)
        run_id = store_geo.start_run(db, bank["version"], note)
        first = True
        try:
            for engine in active:
                failures = []
                for q in questions:
                    for idx in range(1, repeat+1):
                        if not first:
                            time.sleep(interval)
                        first = False
                        sample = engine.ask(q["text"])
                        analysis = {} if sample["error"] else analyze(sample["answer_text"], brand)
                        store_geo.save_sample(db, run_id, q, idx, sample, analysis)
                        if sample["error"]:
                            failures.append(sample["error"])
                            store.record_failure(db, "geo:" + engine.name, sample["error"])
                            log(f'{engine.name} {q["id"]} #{idx}：{sample["error"]}')
                # 本轮有错误时保留退避；全轮成功才重置，避免后续成功掩盖限流。
                if not failures:
                    store.record_success(db, "geo:" + engine.name)
        finally:
            store_geo.finish_run(db, run_id)
        log(build_report(db, run_id))
        return run_id
    finally:
        if owned:
            db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="国内 AI 引擎 GEO 采样")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--engines", default="deepseek,doubao")
    run.add_argument("--groups", default=",".join(GROUPS))
    run.add_argument("--repeat", type=int)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--config", default=str(HERE / "config.yaml"))
    run.add_argument("--questions", default=str(HERE / "questions.yaml"))
    run.add_argument("--brand", default=str(HERE / "brand.yaml"))
    report = sub.add_parser("report")
    report.add_argument("--run", type=int)
    for command in (run, report):
        command.add_argument("--db", default=str(HERE.parent / "guba.db"))
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            run_sampling(args)
        else:
            with sqlite3.connect(args.db) as db:
                store_geo.migrate(db)
                print(build_report(db, args.run))
    except (ValueError, OSError, yaml.YAMLError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
