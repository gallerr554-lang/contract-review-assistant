import httpx

from app.providers.base import ChatMessage, ModelProvider


class OpenAIProvider(ModelProvider):
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("未配置 OpenAI API Key。")
        api_base = (self.api_base or "https://api.openai.com/v1").rstrip("/")
        response = httpx.post(
            f"{api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [message.model_dump() for message in messages],
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=120.0,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"OpenAI API 请求失败（HTTP {response.status_code}）。") from exc
        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenAI API 返回了无法识别的响应。") from exc
