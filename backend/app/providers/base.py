from abc import ABC, abstractmethod

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ProviderRequestError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ModelProvider(ABC):
    def __init__(self, model_name: str, api_base: str | None, api_key: str | None) -> None:
        self.model_name = model_name
        self.api_base = api_base
        self.api_key = api_key

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        raise NotImplementedError
