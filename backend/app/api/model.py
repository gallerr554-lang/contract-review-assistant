from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import SecretConfigurationError, SecretDecryptionError
from app.core.dependencies import AdminUser
from app.database.session import get_db
from app.models.model_config import ModelConfig
from app.schemas.configuration import StatusUpdate
from app.schemas.model_config import (
    ModelConfigCreateRequest,
    ModelConnectionTestResponse,
    ModelConfigResponse,
    ModelConfigUpdateRequest,
)
from app.service.model_service import ModelService
from app.service.model_config_service import (
    ModelConfigNotFoundError,
    ModelConfigService,
    ModelConfigValidationError,
)

router = APIRouter()
model_config_service = ModelConfigService()


def config_response(config: ModelConfig) -> ModelConfigResponse:
    source = model_config_service.key_source(config)
    return ModelConfigResponse(
        id=config.id,
        provider=config.provider,
        model_name=config.model_name,
        api_base=config.api_base,
        api_key_masked=model_config_service.masked_key(config),
        api_key_configured=source != "missing",
        api_key_source=source,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        status=config.status,
        create_time=config.create_time,
        update_time=config.update_time,
    )


@router.get("", response_model=list[ModelConfigResponse])
def list_model_configs(
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
    provider: Literal["openai", "deepseek", "qwen"] | None = None,
    enabled: bool | None = Query(default=None),
) -> list[ModelConfigResponse]:
    return [
        config_response(config)
        for config in model_config_service.list_configs(db, provider, enabled)
    ]


@router.get("/active", response_model=ModelConfigResponse)
def get_active_model_config(
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ModelConfigResponse:
    del admin
    config = model_config_service.get_active(db)
    if not config:
        raise HTTPException(status_code=404, detail="当前没有启用的模型配置。")
    return config_response(config)


@router.post("", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
def create_model_config(
    request: ModelConfigCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ModelConfigResponse:
    del admin
    try:
        return config_response(model_config_service.create_config(db, request))
    except (ModelConfigValidationError, SecretConfigurationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/{config_id}", response_model=ModelConfigResponse)
def update_model_config(
    config_id: int,
    request: ModelConfigUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ModelConfigResponse:
    del admin
    try:
        return config_response(model_config_service.update_config(db, config_id, request))
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ModelConfigValidationError,
        SecretConfigurationError,
        SecretDecryptionError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{config_id}/status", response_model=ModelConfigResponse)
def set_model_config_status(
    config_id: int,
    request: StatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ModelConfigResponse:
    del admin
    try:
        return config_response(model_config_service.set_status(db, config_id, request.status))
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ModelConfigValidationError, SecretDecryptionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{config_id}/test", response_model=ModelConnectionTestResponse)
def test_model_connection(
    config_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: AdminUser,
) -> ModelConnectionTestResponse:
    del admin
    try:
        config = model_config_service.get_config(db, config_id)
        api_key = model_config_service.resolve_api_key(config)
        if not api_key:
            raise ModelConfigValidationError("该模型尚未配置可用的 API Key。")
        service = ModelService(
            provider_name=config.provider,
            model_name=config.model_name,
            api_base=config.api_base,
            api_key=api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        result = service.test_connection()
        return ModelConnectionTestResponse(
            provider=config.provider,
            model_name=config.model_name,
            api_base=config.api_base or "",
            **result,
        )
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ModelConfigValidationError,
        SecretConfigurationError,
        SecretDecryptionError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
