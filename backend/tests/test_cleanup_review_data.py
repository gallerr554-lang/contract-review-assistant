from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.review import ReviewRisk, ReviewRiskFeedback, ReviewTask
from app.models.rule import ReviewRule
from app.models.scene import ReviewScene, SceneRuleRelation
from app.models.user import User
from scripts.cleanup_review_data import CONFIRMATION, cleanup_database, cleanup_storage


def test_confirmation_phrase_is_explicit() -> None:
    assert CONFIRMATION == "DELETE_REVIEW_HISTORY"


def test_cleanup_preserves_users_rules_scenes_and_relations(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db: Session = sessionmaker(bind=engine)()
    user = User(email="cleanup@example.com", password_hash="test", role="user", status=True)
    rule = ReviewRule(
        rule_id="R-CLEANUP",
        rule_name="清理保护规则",
        business_type="合同审查",
        rule_type="AI语义审查",
        risk_level="medium",
        review_requirement="检查清理边界。",
        status=True,
    )
    scene = ReviewScene(
        scene_name="清理保护场景",
        business_type="合同审查",
        system_prompt="仅用于测试。",
        status=True,
        display_order=1,
    )
    db.add_all([user, rule, scene])
    db.flush()
    db.add(SceneRuleRelation(scene_id=scene.id, rule_id=rule.id))
    task = ReviewTask(
        task_no="CR-CLEANUP",
        user_id=user.id,
        upload_id="a" * 36,
        contract_name="待清理合同.txt",
        contract_text="合同正文",
        attachment_names=[],
        attachment_texts=[],
        scene_name=scene.scene_name,
        scene_snapshot={"rules": []},
        model_snapshot={"provider": "deepseek", "model_name": "deepseek-chat"},
        document_pages=[],
        document_meta={},
        document_files=[],
        scale="标准",
        position="甲方",
        status="SUCCESS",
        progress=100,
        current_step=5,
        current_message="完成",
    )
    db.add(task)
    db.flush()
    risk = ReviewRisk(
        task_id=task.id,
        rule_id=rule.rule_id,
        rule_name=rule.rule_name,
        risk_name="测试风险",
        risk_level="medium",
        description="说明",
        suggestion="建议",
    )
    db.add(risk)
    db.flush()
    db.add(
        ReviewRiskFeedback(
            user_id=user.id,
            task_id=task.id,
            risk_id=risk.id,
            rule_id=rule.rule_id,
            content="测试反馈",
        )
    )
    db.commit()

    deleted = cleanup_database(db)

    assert deleted == {"feedback": 1, "risks": 1, "tasks": 1}
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert db.scalar(select(func.count()).select_from(ReviewRule)) == 1
    assert db.scalar(select(func.count()).select_from(ReviewScene)) == 1
    assert db.scalar(select(func.count()).select_from(SceneRuleRelation)) == 1

    for name in ("contracts", "attachments", "results", "tmp", "temp"):
        child = tmp_path / name / "generated"
        child.mkdir(parents=True)
        (child / "artifact.bin").write_bytes(b"test")
    removed = cleanup_storage(tmp_path)
    assert all(count == 1 for count in removed.values())
    assert all(not any((tmp_path / name).iterdir()) for name in removed)
    db.close()
