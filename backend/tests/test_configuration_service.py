from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.scene import SceneRuleRelation
from app.prompts.contract_review import build_review_messages
from app.schemas.configuration import RuleCreateRequest, SceneCreateRequest
from app.schemas.review import ReviewCreateRequest
from app.service.review_service import ReviewService
from app.service.model_service import ModelService
from app.service.rule_service import RuleService
from app.service.scene_service import SceneService


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def create_rule(db: Session, name: str, enabled: bool = True):
    return RuleService().create_rule(
        db,
        RuleCreateRequest(
            rule_name=name,
            rule_type="AI语义审查",
            risk_level="medium",
            review_requirement=f"检查{name}。",
            description=f"{name}说明",
            status=enabled,
        ),
    )


def test_scene_availability_follows_rule_status(db: Session) -> None:
    active_rule = create_rule(db, "付款条件")
    disabled_rule = create_rule(db, "知识产权", enabled=False)
    scene_service = SceneService()
    scene, _ = scene_service.create_scene(
        db,
        SceneCreateRequest(
            scene_name="测试场景",
            description="测试",
            system_prompt="你是测试合同审查专家。",
            rule_ids=[active_rule.id, disabled_rule.id],
            status=True,
            display_order=1,
        ),
    )

    assert [item.id for item in scene_service.list_available(db)] == [scene.id]

    RuleService().set_status(db, active_rule.id, False)

    assert scene_service.list_available(db) == []


def test_delete_rule_removes_scene_relation(db: Session) -> None:
    rule = create_rule(db, "争议解决")
    scene, _ = SceneService().create_scene(
        db,
        SceneCreateRequest(
            scene_name="通用测试",
            system_prompt="你是合同审查专家。",
            rule_ids=[rule.id],
            status=True,
            display_order=2,
        ),
    )

    RuleService().delete_rule(db, rule.id)

    relation_count = db.scalar(
        select(func.count()).select_from(SceneRuleRelation).where(
            SceneRuleRelation.scene_id == scene.id
        )
    )
    assert relation_count == 0
    assert SceneService().list_available(db) == []


def test_review_task_saves_only_enabled_rule_snapshot(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_rule = create_rule(db, "交付验收")
    disabled_rule = create_rule(db, "保密义务", enabled=False)
    scene, _ = SceneService().create_scene(
        db,
        SceneCreateRequest(
            scene_name="技术服务测试",
            system_prompt="你是技术服务合同审查专家。",
            rule_ids=[active_rule.id, disabled_rule.id],
            status=True,
            display_order=1,
        ),
    )

    class FakeFileService:
        @staticmethod
        def load_manifest(upload_id: str, user_id: int) -> dict:
            assert user_id == 1
            return {
                "main_file": {
                    "file_name": "合同.txt",
                    "content": "合同正文",
                    "character_count": 4,
                },
                "attachments": [],
            }

    monkeypatch.setattr(
        ModelService,
        "configuration_snapshot",
        classmethod(
            lambda _cls, _db: {
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "api_base": "https://api.deepseek.com",
                "temperature": 0.2,
                "max_tokens": 4096,
            }
        ),
    )
    task, created = ReviewService(file_service=FakeFileService()).create_task(
        db,
        ReviewCreateRequest(
            upload_id="a" * 36,
            scene_id=scene.id,
            scale="标准",
            position="甲方",
        ),
        1,
        "configuration-snapshot-test",
    )

    assert created is True
    assert task.scene_name == "技术服务测试"
    assert task.scene_snapshot["system_prompt"] == "你是技术服务合同审查专家。"
    assert "user_id" not in task.model_snapshot
    assert "api_key_encrypted" not in task.model_snapshot
    assert [rule["rule_id"] for rule in task.scene_snapshot["rules"]] == [
        active_rule.rule_id
    ]

    messages = build_review_messages(task)
    assert "你是技术服务合同审查专家" in messages[0].content
    assert active_rule.rule_id in messages[1].content
    assert disabled_rule.rule_id not in messages[1].content
