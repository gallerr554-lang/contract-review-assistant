from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import SecretCipher
from app.core.time import utc_now
from app.models.model_config import ModelConfig
from app.schemas.model_config import ModelConfigCreateRequest, ModelConfigUpdateRequest


class ModelConfigNotFoundError(LookupError):
    pass


class ModelConfigValidationError(ValueError):
    pass


class ModelConfigService:
    def __init__(self, cipher: SecretCipher | None = None) -> None:
        self.cipher = cipher or SecretCipher()

    def list_configs(
        self,
        db: Session,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> list[ModelConfig]:
        statement = select(ModelConfig)
        if provider:
            statement = statement.where(ModelConfig.provider == provider)
        if enabled is not None:
            statement = statement.where(ModelConfig.status == enabled)
        return list(db.scalars(statement.order_by(ModelConfig.status.desc(), ModelConfig.id)))

    def create_config(self, db: Session, request: ModelConfigCreateRequest) -> ModelConfig:
        self._ensure_unique(db, request.provider, request.model_name, request.api_base)
        data = request.model_dump(exclude={"api_key"})
        config = ModelConfig(
            **data,
            api_key_encrypted=self.cipher.encrypt(request.api_key),
            create_time=self._now(),
            update_time=self._now(),
        )
        if config.status:
            self._deactivate_all(db)
        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    def update_config(
        self, db: Session, config_id: int, request: ModelConfigUpdateRequest
    ) -> ModelConfig:
        config = self.get_config(db, config_id)
        self._ensure_unique(
            db, request.provider, request.model_name, request.api_base, current_id=config.id
        )
        for field, value in request.model_dump(exclude={"api_key"}).items():
            setattr(config, field, value)
        if request.api_key:
            config.api_key_encrypted = self.cipher.encrypt(request.api_key)
        if request.status:
            self._deactivate_all(db, exclude_id=config.id)
        config.update_time = self._now()
        db.commit()
        db.refresh(config)
        return config

    def set_status(self, db: Session, config_id: int, enabled: bool) -> ModelConfig:
        config = self.get_config(db, config_id)
        if enabled:
            if not self.resolve_api_key(config):
                raise ModelConfigValidationError("该模型尚未配置可用的 API Key。")
            self._deactivate_all(db, exclude_id=config.id)
        config.status = enabled
        config.update_time = self._now()
        db.commit()
        db.refresh(config)
        return config

    @staticmethod
    def get_config(db: Session, config_id: int) -> ModelConfig:
        config = db.get(ModelConfig, config_id)
        if not config:
            raise ModelConfigNotFoundError("模型配置不存在。")
        return config

    @staticmethod
    def get_active(db: Session) -> ModelConfig | None:
        return db.scalar(
            select(ModelConfig)
            .where(ModelConfig.status.is_(True))
            .order_by(ModelConfig.id)
            .limit(1)
        )

    @staticmethod
    def count_configs(db: Session) -> int:
        return int(
            db.scalar(select(func.count()).select_from(ModelConfig))
            or 0
        )

    @staticmethod
    def get_by_identity(
        db: Session, provider: str, model_name: str, api_base: str | None
    ) -> ModelConfig | None:
        return db.scalar(
            select(ModelConfig).where(
                ModelConfig.provider == provider,
                ModelConfig.model_name == model_name,
                ModelConfig.api_base == api_base,
            )
        )

    def resolve_api_key(self, config: ModelConfig) -> str | None:
        if config.api_key_encrypted:
            return self.cipher.decrypt(config.api_key_encrypted)
        if (
            config.provider.lower() == settings.model_provider.lower()
            and config.model_name == settings.model_name
        ):
            return settings.model_api_key
        return None

    def key_source(self, config: ModelConfig) -> str:
        if config.api_key_encrypted:
            return "encrypted"
        if self.resolve_api_key(config):
            return "environment"
        return "missing"

    def masked_key(self, config: ModelConfig) -> str:
        key = self.resolve_api_key(config)
        if not key:
            return "未配置"
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:3]}{'*' * 8}{key[-4:]}"

    def _ensure_unique(
        self,
        db: Session,
        provider: str,
        model_name: str,
        api_base: str,
        current_id: int | None = None,
    ) -> None:
        statement = select(ModelConfig.id).where(
            ModelConfig.provider == provider,
            ModelConfig.model_name == model_name,
            ModelConfig.api_base == api_base,
        )
        if current_id is not None:
            statement = statement.where(ModelConfig.id != current_id)
        if db.scalar(statement):
            raise ModelConfigValidationError("相同 Provider、模型名称和 API Base 已存在。")

    @staticmethod
    def _deactivate_all(db: Session, exclude_id: int | None = None) -> None:
        statement = update(ModelConfig).where(ModelConfig.status.is_(True))
        if exclude_id is not None:
            statement = statement.where(ModelConfig.id != exclude_id)
        db.execute(statement.values(status=False, update_time=ModelConfigService._now()))

    @staticmethod
    def _now() -> datetime:
        return utc_now()
