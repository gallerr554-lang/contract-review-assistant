from app.core.config import settings
from app.database.session import SessionLocal
from app.providers.base import ChatMessage, ModelProvider, ProviderRequestError
from app.providers.deepseek_provider import DeepSeekProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.qwen_provider import QwenProvider
from app.service.model_config_service import ModelConfigService


class ModelConfigurationError(ValueError):
    pass


class ModelService:
    def __init__(
        self,
        provider_name: str,
        model_name: str,
        api_base: str | None,
        api_key: str | None,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.api_base = api_base
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider = self._build_provider()

    @classmethod
    def from_settings(cls) -> "ModelService":
        return cls(
            provider_name=settings.model_provider,
            model_name=settings.model_name,
            api_base=settings.model_api_base,
            api_key=settings.model_api_key,
            temperature=settings.model_temperature,
            max_tokens=settings.model_max_tokens,
        )

    @classmethod
    def from_database(cls) -> "ModelService":
        db = SessionLocal()
        try:
            return cls._from_active_config(db)
        finally:
            db.close()

    @classmethod
    def from_snapshot(cls, db, snapshot: dict | None) -> "ModelService":
        snapshot = snapshot or {}
        if snapshot.get("provider") and snapshot.get("model_name"):
            config_service = ModelConfigService()
            config = config_service.get_by_identity(
                db,
                str(snapshot["provider"]),
                str(snapshot["model_name"]),
                snapshot.get("api_base"),
            )
            if not config:
                raise ModelConfigurationError("任务使用的模型配置已不存在，请重新发起审查。")
            api_key = config_service.resolve_api_key(config)
            if not api_key:
                raise ModelConfigurationError("任务使用的模型尚未配置可用 API Key。")
            return cls(
                provider_name=str(snapshot["provider"]),
                model_name=str(snapshot["model_name"]),
                api_base=snapshot.get("api_base"),
                api_key=api_key,
                temperature=float(snapshot.get("temperature", config.temperature)),
                max_tokens=int(snapshot.get("max_tokens", config.max_tokens)),
            )
        return cls._from_active_config(db)

    @classmethod
    def configuration_snapshot(cls, db) -> dict:
        config_service = ModelConfigService()
        config = config_service.get_active(db)
        if config:
            api_key = config_service.resolve_api_key(config)
            if not api_key:
                raise ModelConfigurationError("当前启用模型尚未配置可用 API Key。")
            snapshot = {
                "provider": config.provider,
                "model_name": config.model_name,
                "api_base": config.api_base,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            }
            return snapshot
        if config_service.count_configs(db):
            raise ModelConfigurationError("当前没有启用的模型配置。")
        raise ModelConfigurationError("系统尚未配置可用模型，请联系管理员。")

    def chat(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self.provider.chat(
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
        )

    def public_config(self) -> dict[str, str | float | int | None]:
        return {
            "provider": self.provider_name,
            "model_name": self.model_name,
            "api_base": self.api_base,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def test_connection(self) -> dict[str, str | int | bool | None]:
        try:
            content = self.chat(
                [
                    ChatMessage(role="system", content="Return one JSON object only."),
                    ChatMessage(role="user", content='Return {"ok":true}.'),
                ],
                temperature=0,
                max_tokens=64,
            )
            if not content.strip():
                raise ProviderRequestError("模型接口返回了空响应。", 200)
            return {
                "success": True,
                "http_status": 200,
                "message": "连接成功",
            }
        except ProviderRequestError as exc:
            return {
                "success": False,
                "http_status": exc.status_code,
                "message": str(exc),
            }
        except Exception:
            return {
                "success": False,
                "http_status": None,
                "message": "模型连接测试失败，请检查配置或后端日志。",
            }

    def _build_provider(self) -> ModelProvider:
        provider_name = self.provider_name.lower()
        provider_map = {
            "openai": OpenAIProvider,
            "deepseek": DeepSeekProvider,
            "qwen": QwenProvider,
        }
        provider_class = provider_map.get(provider_name)
        if not provider_class:
            raise ModelConfigurationError(f"不支持的模型 Provider：{self.provider_name}")
        return provider_class(
            model_name=self.model_name,
            api_base=self.api_base,
            api_key=self.api_key,
        )

    @classmethod
    def _from_active_config(cls, db) -> "ModelService":
        snapshot = cls.configuration_snapshot(db)
        return cls.from_snapshot(db, snapshot)
