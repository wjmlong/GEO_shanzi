"""股吧文本情绪打分：金融/股吧词典 + 否定词 + 程度副词。

规则方法速度快、零成本，但对反讽（如“大盘涨了1%，你涨了2分钱”）判断不准，
score 接近 0 的帖子可以再交给大模型复判。
"""

POSITIVE = {
    "涨停": 2, "暴涨": 2, "大涨": 2, "翻倍": 2, "利好": 2, "起飞": 2, "主升浪": 2,
    "龙头": 1.5, "突破": 1.5, "反转": 1.5, "抄底": 1.5, "加仓": 1.5, "满仓": 1.5,
    "看好": 1.5, "看多": 1.5, "牛股": 1.5, "业绩增长": 1.5, "扭亏": 1.5, "回购": 1.5,
    "增持": 1.5, "坚定持有": 1.5, "反弹": 1, "上涨": 1, "拉升": 1, "红盘": 1, "稳了": 1,
    "机会": 1, "低估": 1, "有戏": 1, "拿住": 1, "赚钱": 1, "盈利": 1, "牛": 1,
    "希望": 1, "期待": 0.8, "不错": 0.8, "挺好": 0.8, "涨": 0.4,
}
NEGATIVE = {
    "退市": 2.5, "爆雷": 2.5, "立案": 2.5, "造假": 2.5, "跌停": 2, "暴跌": 2, "大跌": 2,
    "骗子": 2, "垃圾": 2, "割韭菜": 2, "巨亏": 2, "利空": 2, "跑路": 2, "崩盘": 2,
    "庄家出货": 2, "强平": 2, "割肉": 1.5, "套牢": 1.5, "被套": 1.5, "亏损": 1.5,
    "减持": 1.5, "清仓": 1.5, "跳水": 1.5, "崩": 1.5, "阴跌": 1.5, "破位": 1.5,
    "新低": 1.5, "完了": 1.5, "凉了": 1.5, "绝望": 1.5, "违规": 1.5, "处罚": 1.5,
    "冻结": 1.5, "出货": 1.2, "接盘": 1.2, "坑": 1.2, "失望": 1.2, "后悔": 1.2,
    "诉讼": 1.2, "下跌": 1, "绿盘": 1, "亏": 1, "跌": 0.4,
}
NEGATIONS = ("不", "没", "无", "别", "非", "未", "勿", "难")
DEGREE = {"极其": 2.0, "非常": 1.5, "特别": 1.5, "太": 1.5, "超": 1.5, "很": 1.3,
          "真": 1.2, "有点": 0.7, "稍微": 0.6, "略": 0.6}

_LEX = {**POSITIVE, **{w: -v for w, v in NEGATIVE.items()}}
_MAXLEN = max(map(len, _LEX))


def score(text):
    """返回 (score, label, hits)。score > 0 偏多，< 0 偏空。"""
    text = (text or "").lower()
    total, hits, i, last_end = 0.0, [], 0, 0
    while i < len(text):
        for n in range(min(_MAXLEN, len(text) - i), 0, -1):
            word = text[i:i + n]
            if word not in _LEX:
                continue
            value = _LEX[word]
            window = text[max(last_end, i - 4):i]
            neg_window = window
            for d in DEGREE:  # “非常”里的“非”不算否定
                neg_window = neg_window.replace(d, "")
            if any(neg in neg_window for neg in NEGATIONS):
                value = -value
            for d, k in DEGREE.items():
                if d in window:
                    value *= k
                    break
            total += value
            hits.append(word)
            i += n
            last_end = i
            break
        else:
            i += 1
    label = "正面" if total >= 1 else "负面" if total <= -1 else "中性"
    return round(total, 2), label, hits
