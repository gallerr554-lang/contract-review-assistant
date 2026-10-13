from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
import httpx
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models import Base
from app.models.model_config import ModelConfig
from app.models.review import ReviewRisk, ReviewTask
from app.models.user import User
from app.providers.base import ChatMessage, ProviderRequestError
from app.providers.deepseek_provider import DeepSeekProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.qwen_provider import QwenProvider, normalize_qwen_api_base
from app.schemas.model_config import ModelConfigCreateRequest
from app.schemas.review import RiskFeedbackCreateRequest
from app.service.model_config_service import ModelConfigService
from app.service.model_service import ModelService
from app.service.review_record_service import (
    ReviewRecordService,
    ReviewRecordValidationError,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def create_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="test", role="user", status=True)
    db.add(user)
    db.flush()
    return user


def create_task(
    db: Session, name: str, status: str, offset: int = 0, user_id: int | None = None
) -> ReviewTask:
    task = ReviewTask(
        task_no=f"CR-{name}-{offset}",
        user_id=user_id,
        upload_id="a" * 36,
        contract_name=name,
        contract_text="合同正文",
        attachment_names=[],
        attachment_texts=[],
        scene_name="历史场景快照",
        scene_snapshot={"scene_name": "历史场景快照", "rules": []},
        model_snapshot={"provider": "deepseek", "model_name": "deepseek-chat"},
        scale="标准",
        position="甲方",
        status=status,
        progress=100 if status == "SUCCESS" else 40,
        current_step=5 if status == "SUCCESS" else 2,
        current_message="测试",
        error_message="模型响应异常" if status == "FAILED" else None,
        create_time=datetime(2026, 8, 4, 12, 0) + timedelta(minutes=offset),
    )
    db.add(task)
    db.flush()
    return task


def add_risk(db: Session, task: ReviewTask, level: str, rule_id: str) -> ReviewRisk:
    risk = ReviewRisk(
        task_id=task.id,
        rule_id=rule_id,
        rule_name="测试规则",
        risk_name=f"{level}风险",
        risk_level=level,
        original_text="合同正文",
        source=task.contract_name,
        locatable=True,
        description="风险说明",
        suggestion="修改建议",
    )
    db.add(risk)
    db.flush()
    return risk


def test_history_filters_and_aggregates_risks(db: Session) -> None:
    user = create_user(db, "history@example.com")
    other = create_user(db, "other@example.com")
    success = create_task(db, "技术服务合同.txt", "SUCCESS", 1, user.id)
    create_task(db, "采购合同.txt", "FAILED", 2, user.id)
    create_task(db, "其他用户合同.txt", "SUCCESS", 3, other.id)
    add_risk(db, success, "high", "R001")
    add_risk(db, success, "high", "R002")
    add_risk(db, success, "medium", "R003")
    db.commit()

    items, total = ReviewRecordService().list_history(
        db, user.id, keyword="技术服务", status="SUCCESS"
    )

    assert total == 1
    assert items[0].scene_name == "历史场景快照"
    assert items[0].risk_total == 3
    assert items[0].high_risk_count == 2
    assert items[0].medium_risk_count == 1
    assert items[0].low_risk_count == 0


def test_feedback_is_idempotent_and_requires_success_task(db: Session) -> None:
    user = create_user(db, "feedback@example.com")
    success = create_task(db, "成功合同.txt", "SUCCESS", user_id=user.id)
    failed = create_task(db, "失败合同.txt", "FAILED", 1, user.id)
    success_risk = add_risk(db, success, "high", "R001")
    failed_risk = add_risk(db, failed, "medium", "R002")
    db.commit()
    service = ReviewRecordService()
    request = RiskFeedbackCreateRequest(content="该规则不适用于当前交易。")

    first = service.create_feedback(db, user.id, success.id, success_risk.id, request)
    second = service.create_feedback(db, user.id, success.id, success_risk.id, request)

    assert first.id == second.id
    assert first.rule_id == "R001"
    with pytest.raises(ReviewRecordValidationError, match="已完成"):
        service.create_feedback(db, user.id, failed.id, failed_risk.id, request)


def model_request(provider: str, model_name: str, api_key: str, status: bool):
    base = {
        "deepseek": "https://api.deepseek.com",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }[provider]
    return ModelConfigCreateRequest(
        provider=provider,
        model_name=model_name,
        api_base=base,
        api_key=api_key,
        temperature=0.3,
        max_tokens=2048,
        status=status,
    )


def test_model_keys_are_encrypted_and_active_model_is_singleton(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    encryption_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(settings, "model_config_encryption_key", encryption_key)
    service = ModelConfigService()
    deepseek = service.create_config(
        db, model_request("deepseek", "deepseek-chat", "deepseek-secret", True)
    )
    qwen = service.create_config(
        db, model_request("qwen", "qwen-plus", "qwen-secret", True)
    )

    db.refresh(deepseek)
    assert deepseek.status is False
    assert qwen.status is True
    assert qwen.api_key_encrypted != "qwen-secret"
    assert service.resolve_api_key(qwen) == "qwen-secret"
    assert "qwen-secret" not in service.masked_key(qwen)

    assert [item.id for item in service.list_configs(db)] == [qwen.id, deepseek.id]
    snapshot = ModelService.configuration_snapshot(db)
    assert "user_id" not in snapshot
    assert "api_key_encrypted" not in snapshot
    assert "qwen-secret" not in str(snapshot)

    qwen.api_key_encrypted = service.cipher.encrypt("rotated-secret")
    db.commit()
    model_service = ModelService.from_snapshot(db, snapshot)
    assert isinstance(model_service.provider, QwenProvider)
    assert model_service.api_key == "rotated-secret"

    service.set_status(db, qwen.id, False)
    assert service.get_active(db) is None
    service.set_status(db, deepseek.id, True)
    assert service.get_active(db).id == deepseek.id


def test_openai_provider_uses_completion_token_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_payload: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {"choices": [{"message": {"content": '{"risks": []}'}}]}

    def fake_post(*_args, **kwargs):
        request_payload.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr("app.providers.openai_provider.httpx.post", fake_post)
    provider = OpenAIProvider(
        model_name="gpt-4.1",
        api_base="https://api.openai.com/v1",
        api_key="test-key",
    )

    result = provider.chat(
        [ChatMessage(role="user", content="review")],
        temperature=0.2,
        max_tokens=2048,
    )

    assert result == '{"risks": []}'
    assert request_payload["max_completion_tokens"] == 2048
    assert "max_tokens" not in request_payload


def test_qwen_provider_uses_configured_region_model_key_and_structured_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("app.providers.qwen_provider.httpx.post", fake_post)
    provider = QwenProvider(
        model_name="qwen3.7-plus",
        api_base="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/",
        api_key="qwen-test-secret",
    )

    result = provider.chat(
        [ChatMessage(role="user", content="review")], temperature=0.2, max_tokens=2048
    )

    assert result == '{"ok":true}'
    assert captured["url"] == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    assert captured["headers"]["Authorization"] == "Bearer qwen-test-secret"
    assert captured["json"]["model"] == "qwen3.7-plus"
    assert captured["json"]["max_tokens"] == 2048
    assert captured["json"]["enable_thinking"] is False
    assert normalize_qwen_api_base("https://dashscope-us.aliyuncs.com") == (
        "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    )


def test_qwen_failure_is_sanitized_and_never_falls_back_to_deepseek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "qwen-secret-that-must-not-leak"
    request = httpx.Request("POST", "https://dashscope.aliyuncs.com")
    response = httpx.Response(
        401,
        request=request,
        json={"error": {"message": f"invalid token {key}"}},
    )
    deepseek_called = False

    def qwen_post(*_args, **_kwargs):
        return response

    def deepseek_chat(*_args, **_kwargs):
        nonlocal deepseek_called
        deepseek_called = True
        raise AssertionError("Qwen failure must not call DeepSeek")

    monkeypatch.setattr("app.providers.qwen_provider.httpx.post", qwen_post)
    monkeypatch.setattr(DeepSeekProvider, "chat", deepseek_chat)
    service = ModelService(
        "qwen",
        "qwen-plus",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        key,
        0.2,
        128,
    )

    with pytest.raises(ProviderRequestError) as exc_info:
        service.chat([ChatMessage(role="user", content="review")])

    assert exc_info.value.status_code == 401
    assert key not in str(exc_info.value)
    assert isinstance(service.provider, QwenProvider)
    assert deepseek_called is False


def test_environment_model_snapshot_does_not_require_encryption_key(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = ModelConfig(
        provider="deepseek",
        model_name="deepseek-chat",
        api_base="https://api.deepseek.com",
        api_key_encrypted=None,
        temperature=0.2,
        max_tokens=4096,
        status=True,
    )
    db.add(config)
    db.commit()
    monkeypatch.setattr(settings, "model_provider", "deepseek")
    monkeypatch.setattr(settings, "model_name", "deepseek-chat")
    monkeypatch.setattr(settings, "model_api_key", "environment-secret")
    monkeypatch.setattr(settings, "model_config_encryption_key", None)

    snapshot = ModelService.configuration_snapshot(db)
    service = ModelService.from_snapshot(db, snapshot)

    assert "api_key_encrypted" not in snapshot
    assert service.api_key == "environment-secret"


def test_deepseek_provider_rejects_non_ascii_placeholder_key() -> None:
    provider = DeepSeekProvider(
        model_name="deepseek-chat",
        api_base="https://api.deepseek.com",
        api_key="请填写真实密钥",
    )

    with pytest.raises(RuntimeError, match="格式无效"):
        provider.chat(
            [ChatMessage(role="user", content="review")],
            temperature=0.2,
            max_tokens=128,
        )
