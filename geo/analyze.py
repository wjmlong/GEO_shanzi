"""规则分析，不进行联网或模型复判。"""
import re
from collections import Counter
from urllib.parse import urlsplit

import yaml
import sentiment

from sentiment import score


def load_brand(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def analyze_answer(text, brand):
    """按最长别名优先统计不重叠命中，域名保留子域并去重保序。"""
    hits = matches(text, [brand["name"]] + brand.get("aliases", []))
    competitors = []
    for entry in brand.get("competitors", []):
        item = {"name": entry} if isinstance(entry, str) else entry
        if matches(text, [item["name"]] + item.get("aliases", [])):
            if item["name"] not in competitors:
                competitors.append(item["name"])
    domains = []
    for match in re.finditer(r'https?://[^\s<>"\[\]（）()，。；！？、]+', text, re.I):
        try:
            host = urlsplit(match[0].rstrip(".,;:!?'")).hostname
        except ValueError:
            continue
        if host and host not in domains:
            domains.append(host)
    value, label, _ = sentiment.score(text)
    return dict(mentioned=bool(hits), first_pos=hits[0].start() if hits else None,
                mention_count=len(hits), competitors=competitors, domains=domains,
                score=value, label=label)


def matches(text, aliases):
    parts = [r"(?<!\d)" + re.escape(a) + r"(?!\d)" if a.isdigit() else re.escape(a)
             for a in sorted(set(aliases), key=len, reverse=True) if a]
    return list(re.finditer("|".join(parts), text, re.I)) if parts else []


def analyze(text, brand, hook=None):
    hits = matches(text, [brand["name"]] + brand.get("aliases", []))
    competitors = {}
    for entry in brand.get("competitors", []):
        item = {"name": entry} if isinstance(entry, str) else entry
        found = matches(text, [item["name"]] + item.get("aliases", []))
        if found:
            competitors[item["name"]] = {"count": len(found), "first_pos": found[0].start()}
    # 仅在显式编号行以品牌开头时提供列表名次，不推断未知公司实体。
    rank = None
    if hits:
        line = text[text.rfind("\n", 0, hits[0].start()) + 1:hits[0].start()]
        match = re.fullmatch(r"\s*(\d+)[.、)）]\s*(?:\*\*)?", line)
        if match:
            rank = int(match[1])
    pattern = r"https?://[^\s<>\[\]（）()\u3000-\u9fff]+|(?<![\w@.-])(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}(?![a-zA-Z0-9-])"
    urls = [m[0].rstrip('.,;:!?\"\'') for m in re.finditer(pattern, text)]
    domains = Counter()
    for url in urls:
        try:
            host = urlsplit(url if "://" in url else "https://" + url).hostname
            if host:
                domains[host.lower().removeprefix("www.")] += 1
        except ValueError:
            pass
    value, label, _ = score(text)
    result = dict(mentioned=bool(hits), first_pos=hits[0].start() if hits else None,
                  company_rank=rank, mention_count=len(hits), competitors=competitors,
                  urls=urls, domains=dict(domains), score=value, label=label)
    if hook is not None:  # 默认关闭，命令行不启用二次模型判断。
        result["hook"] = hook(text, result)
    return result
