import re
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.providers.base import ChatMessage, ModelProvider, ProviderRequestError


def normalize_qwen_api_base(api_base: str | None) -> str:
    raw = (api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/compatible-mode/v1"
    elif path == "/compatible-mode":
        path = "/compatible-mode/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def qwen_chat_endpoint(api_base: str | None) -> str:
    base = normalize_qwen_api_base(api_base)
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _safe_error_message(response: httpx.Response, api_key: str) -> str:
    detail = ""
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        detail = str(error.get("message") or payload.get("message") or "")
    except (ValueError, TypeError, AttributeError):
        detail = ""
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = re.sub(r"sk-[A-Za-z0-9._-]{8,}", "[REDACTED]", detail)
    detail = " ".join(detail.split())[:240]
    return detail


class QwenProvider(ModelProvider):
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("未配置 Qwen API Key。")
        payload = {
            "model": self.model_name,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if re.match(r"^qwen3(?:[.-]|$)", self.model_name, flags=re.IGNORECASE):
            payload["enable_thinking"] = False
        try:
            response = httpx.post(
                qwen_chat_endpoint(self.api_base),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=httpx.Timeout(
                    connect=20.0,
                    read=float(settings.model_request_timeout_seconds),
                    write=60.0,
                    pool=20.0,
                ),
            )
        except httpx.TimeoutException as exc:
            raise ProviderRequestError("Qwen API 响应超时，请检查地域地址、模型名称或稍后重试。") from exc
        except httpx.RequestError as exc:
            raise ProviderRequestError("Qwen API 连接失败，请检查接口地址和网络。") from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _safe_error_message(response, self.api_key)
            suffix = f"：{detail}" if detail else "。"
            raise ProviderRequestError(
                f"Qwen API 请求失败（HTTP {response.status_code}）{suffix}",
                response.status_code,
            ) from exc
        response_payload = response.json()
        try:
            content = response_payload["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text = "".join(
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, dict)
                )
                if text:
                    return text
            raise TypeError
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderRequestError("Qwen API 返回了无法识别的响应。", response.status_code) from exc
