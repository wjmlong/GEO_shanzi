"""OpenAI 兼容接口；不依赖 openai SDK。"""
import os
import time
from datetime import datetime

import requests


class Engine:
    name = ""
    base_url = ""
    key_env = ""
    default_model = ""

    def __init__(self, config=None):
        self.config = config or {}
        self.key = os.environ.get(self.key_env, "").strip()
        self.model = self.config.get("model") or self.default_model
        self.web_search = self.config.get("web_search", "off")
        self.temperature = self.config.get("temperature", 0.7)
        if self.web_search not in ("off", "on"):
            raise ValueError("web_search 必须为 off 或 on（YAML 中请加引号）")
        extra = self.config.get("extra_body", {})
        if not isinstance(extra, dict) or set(extra) & {"model", "messages", "temperature", "stream"}:
            raise ValueError("extra_body 必须为对象，且不能覆盖基础请求字段")
        if self.web_search == "on" and not extra:
            raise ValueError("联网参数待按官方文档核实：on 模式必须配置 extra_body")

    def unavailable(self):
        return f"缺少 {self.key_env}" if not self.key else ("缺少模型配置" if not self.model else None)

    def ask(self, question):
        body = {"model": self.model, "messages": [{"role": "user", "content": question}],
                "temperature": self.temperature, "stream": False}
        # 联网参数待按官方文档核实；仅 on 模式原样透传配置，不猜测参数名。
        if self.web_search == "on":
            body.update(self.config.get("extra_body", {}))
        result = dict(engine=self.name, model=self.model, web_search=self.web_search,
                      temperature=self.temperature, asked_at=datetime.now().isoformat(),
                      answer_text="", raw_json=None, tokens_in=None, tokens_out=None, error=None)
        attempts = []
        started = time.monotonic()
        for attempt in range(4):  # 首次请求之外，最多重试三次。
            stamp = datetime.now().isoformat()
            tick = time.monotonic()
            raw, status, error = None, None, None
            try:
                response = requests.post(self.base_url.rstrip("/") + "/chat/completions",
                                         headers={"Authorization": f"Bearer {self.key}"},
                                         json=body, timeout=self.config.get("timeout", 60))
                status = response.status_code
                try:
                    raw = response.json()
                except ValueError:
                    raw = {"response_text": response.text}
                if status >= 400:
                    error = f"HTTP {status}"
                else:
                    answer = raw["choices"][0]["message"]["content"]
                    if not isinstance(answer, str) or not answer.strip():
                        raise ValueError("回答为空或不是文本")
                    result["answer_text"] = answer
                    usage = raw.get("usage") or {}
                    result.update(tokens_in=usage.get("prompt_tokens"), tokens_out=usage.get("completion_tokens"))
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
                # 不保存异常全文，避免请求异常意外带出鉴权信息。
                error = type(exc).__name__
            attempts.append(dict(asked_at=stamp, latency_ms=round((time.monotonic()-tick)*1000),
                                 raw_json=raw, error=error, status=status))
            result.update(raw_json=raw, error=error)
            if error and (status == 429 or status is not None and 500 <= status < 600) and attempt < 3:
                time.sleep(max(self.config.get("interval", 1), 2 ** attempt))
                continue
            break
        result["latency_ms"] = round((time.monotonic()-started)*1000)
        result["attempts"] = attempts
        return result


class DeepSeekEngine(Engine):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
    key_env = "DEEPSEEK_API_KEY"
    default_model = "deepseek-chat"


class DoubaoEngine(Engine):
    name = "doubao"
    base_url = "https://ark.cn-beijing.volces.com/api/v3"
    key_env = "ARK_API_KEY"

    def __init__(self, config=None):
        super().__init__(dict(config or {}, model=os.environ.get("DOUBAO_ENDPOINT_ID", "").strip()))

    def unavailable(self):
        return super().unavailable() if self.model else "缺少 DOUBAO_ENDPOINT_ID"
