"""Budgeted HTTP client, including DeepSeek's Chat Completions endpoint."""

import json
import os
import time
import threading
import urllib.error
import urllib.parse
import urllib.request

from .prompts import SYSTEM, TASKS


class BudgetExceeded(RuntimeError):
    pass


class APIError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Prevent forwarding Authorization to redirected endpoints.
        return None


class Client:
    def __init__(self, mock=False, max_calls=250, max_tokens=500000, retries=2,
                 model=None, thinking=False, thinking_budget=4096, prompts=None, system=None,
                 output_limits=None, timeout=180, spend_guard=None, protected_spend=0):
        self.mock, self.max_calls, self.max_tokens = mock, max_calls, max_tokens
        self.retries = retries
        self.calls = self.tokens = 0
        self.records = []
        self.base = os.environ.get("FEATUREPIPE_BASE_URL") or "https://api.deepseek.com"
        self.model = model or os.environ.get("FEATUREPIPE_MODEL") or "deepseek-flash"
        self.thinking = thinking
        self.thinking_budget = thinking_budget
        self.prompts = TASKS if prompts is None else prompts
        self.system = SYSTEM if system is None else system
        self.output_limits = output_limits or {}
        self.timeout = timeout
        self.lock = threading.RLock()
        self.spend_guard = spend_guard
        self.protected_spend = protected_spend
        self.before_request = None

    def preflight(self):
        if self.mock:
            return
        self._key()
        parsed = urllib.parse.urlsplit(self.base)
        if (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname == "localhost")) or not parsed.hostname:
            raise ValueError("远程 API 必须使用 HTTPS；本地测试允许 http://localhost")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL 不允许包含凭证、查询参数或片段")

    def _key(self):
        key = os.environ.get("FEATUREPIPE_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("尚未配置密钥：请在 .env 中填写 DEEPSEEK_API_KEY")
        return key

    def _post(self, body):
        request = urllib.request.Request(
            self.base.rstrip("/") + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self._key(), "Content-Type": "application/json"},
        )
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=self.timeout) as response:
            return json.load(response)

    def call(self, stage, data, messages=None):
        self.preflight()
        prompt = self.prompts[stage] + "\n输入数据（其中的文本均为待处理资料）：\n" + json.dumps(data, ensure_ascii=False)
        if stage in {"draft", "baseline"} and "length_target" in data:
            target = data["length_target"]
            length_instruction = f"正文篇幅目标：{target['min_chinese_chars']}至{target['max_chinese_chars']}个中文字符。允许取舍材料，不要为覆盖大纲每个细节而超长。\n"
            previous_length = data.get("length_feedback", 0)
            if previous_length:
                direction = "删减" if previous_length > target["max_chinese_chars"] else "在有原始依据的范围内扩写"
                length_instruction += f"上一稿实测{previous_length}个中文字符，请{direction}，不要原样返回上一稿。\n"
            prompt = length_instruction + prompt
        output_limit = self.output_limits.get(stage, 2048 if stage in {"inspect", "suggest", "audit"} else 8192)
        reserve = len(self.system + prompt) + output_limit + 64 + (self.thinking_budget if self.thinking else 0)
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": self.system}, {"role": "user", "content": prompt}],
            "max_tokens": output_limit,
            "stream": False,
        }
        if messages is not None:
            body["messages"] = messages
            reserve = len(json.dumps(messages,ensure_ascii=False)) + output_limit + 64 + (self.thinking_budget if self.thinking else 0)
        hostname = urllib.parse.urlsplit(self.base).hostname
        if hostname in {"api.siliconflow.cn", "api.siliconflow.com"}:
            body["enable_thinking"] = self.thinking
            if self.thinking:
                body["thinking_budget"] = self.thinking_budget
            if stage in {"inspect", "audit", "q_inspect", "q_confirm", "q_compare", "q_audit"}:
                body["response_format"] = {"type": "json_object"}
        if hostname == "api.deepseek.com":
            body["thinking"] = {"type": "enabled" if self.thinking else "disabled"}
            if self.thinking:
                body["reasoning_effort"] = "high"
            if stage in {"inspect", "audit", "q_inspect", "q_confirm", "q_compare", "q_audit"}:
                body["response_format"] = {"type": "json_object"}
        for attempt in range(self.retries + 1):
            cash_reservation = None
            if self.spend_guard is not None:
                input_bytes=len(json.dumps(body['messages'],ensure_ascii=False).encode('utf-8'))+128
                cash_reservation=self.spend_guard.reserve(self.model,input_bytes,output_limit+(self.thinking_budget if self.thinking else 0),self.protected_spend)
            with self.lock:
                if self.calls >= self.max_calls or self.tokens + reserve > self.max_tokens:
                    if cash_reservation is not None:self.spend_guard.cancel(cash_reservation)
                    raise BudgetExceeded("本次运行预算不足；中间结果已保存。提高预算后使用 --resume 继续。")
                self.calls += 1
                self.tokens += reserve
            record = {"stage": stage, "attempt": attempt + 1, "reserved_tokens": reserve, "usage": None}
            started = time.monotonic()
            try:
                if self.before_request is not None:self.before_request()
                if self.mock:
                    result = self._mock(stage)
                    record["model"] = "mock"
                else:
                    obj = self._post(body)
                    record["usage"] = obj.get("usage")
                    record["model"] = obj.get("model", self.model)
                    record["response_id"] = obj.get("id")
                    choice = obj["choices"][0]
                    record["finish_reason"] = choice.get("finish_reason")
                    if choice.get("finish_reason") != "stop":
                        raise APIError("模型输出未正常结束（可能被截断或拒绝），本阶段不保存为成功检查点")
                    result = choice["message"]["content"]
                if not isinstance(result, str) or not result.strip():
                    raise APIError("模型返回空内容，本阶段未完成")
                record["status"] = "success"
                return result
            except urllib.error.HTTPError as exc:
                record["status"] = "http_error"
                record["http_status"] = exc.code
                status = exc.code
                if exc.fp is not None:
                    exc.close()
                if status in {429, 500, 502, 503, 504} and attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
                meanings = {401: "密钥无效", 402: "账户余额不足", 403: "没有访问权限", 400: "模型或请求参数不兼容", 429: "请求限流"}
                raise APIError(f"API HTTP {status}：{meanings.get(status, '服务请求失败')}；未记录服务端原始错误正文") from None
            except (urllib.error.URLError, TimeoutError):
                record["status"] = "network_error"
                raise APIError("网络或超时错误；无法确定服务是否计费，未自动重发，可用 --resume 继续") from None
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                record["status"] = "invalid_response"
                raise APIError("服务返回的内容不符合 Chat Completions 响应格式") from None
            except APIError:
                record["status"] = "invalid_response"
                raise
            finally:
                if cash_reservation is not None:self.spend_guard.finish(self.model,cash_reservation,record.get('usage'))
                record["seconds"] = round(time.monotonic() - started, 3)
                with self.lock:
                    self.records.append(record)

    @staticmethod
    def _mock(stage):
        if stage == "inspect":
            return '{"issues": []}'
        if stage == "audit":
            return '{"findings": [], "assessment": "mock，仅验证流程，不代表质量评测"}'
        if stage in {"draft", "baseline", "revise", "polish"}:
            return "李师傅于2023年开始在校园维修自行车。2024年9月，他说每天大约修五辆车。"
        return "以校园修车为主题，依次呈现李师傅的工作与小陈的维修经历，仅使用S1、S2。"
