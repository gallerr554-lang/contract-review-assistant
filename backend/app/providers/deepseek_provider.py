import httpx

from app.providers.base import ChatMessage, ModelProvider


class DeepSeekProvider(ModelProvider):
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("未配置 DeepSeek API Key，请在模型配置中填写或设置环境变量。")
        if not self.api_key.isascii():
            raise RuntimeError("DeepSeek API Key 格式无效，请重新配置。")

        api_base = (self.api_base or "https://api.deepseek.com").rstrip("/")
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
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=120.0,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"DeepSeek API 请求失败（HTTP {response.status_code}）。") from exc

        payload = response.json()
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("DeepSeek API 返回了无法识别的响应。") from exc
