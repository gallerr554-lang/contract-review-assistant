from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.models.rule import ReviewRule
from app.core.time import utc_now
from app.models.scene import ReviewScene, SceneRuleRelation
from app.schemas.configuration import RuleCreateRequest, RuleUpdateRequest


class RuleNotFoundError(LookupError):
    pass


class RuleConflictError(ValueError):
    pass


class RuleService:
    def list_rules(
        self,
        db: Session,
        keyword: str | None = None,
        rule_type: str | None = None,
        risk_level: str | None = None,
        enabled: bool | None = None,
    ) -> list[ReviewRule]:
        statement = select(ReviewRule)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            statement = statement.where(
                or_(ReviewRule.rule_id.ilike(pattern), ReviewRule.rule_name.ilike(pattern))
            )
        if rule_type:
            statement = statement.where(ReviewRule.rule_type == rule_type)
        if risk_level:
            statement = statement.where(ReviewRule.risk_level == risk_level)
        if enabled is not None:
            statement = statement.where(ReviewRule.status == enabled)
        return list(db.scalars(statement.order_by(ReviewRule.rule_id)))

    def create_rule(self, db: Session, request: RuleCreateRequest) -> ReviewRule:
        rule = ReviewRule(rule_id=self._make_rule_id(), **request.model_dump())
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return rule

    def update_rule(
        self, db: Session, rule_id: int, request: RuleUpdateRequest
    ) -> ReviewRule:
        rule = self.get_rule(db, rule_id)
        for field, value in request.model_dump().items():
            setattr(rule, field, value)
        rule.update_time = utc_now()
        db.commit()
        db.refresh(rule)
        return rule

    def set_status(self, db: Session, rule_id: int, enabled: bool) -> ReviewRule:
        rule = self.get_rule(db, rule_id)
        rule.status = enabled
        rule.update_time = utc_now()
        db.commit()
        db.refresh(rule)
        return rule

    def delete_rule(self, db: Session, rule_id: int) -> None:
        rule = self.get_rule(db, rule_id)
        scene_ids = list(
            db.scalars(
                select(SceneRuleRelation.scene_id).where(SceneRuleRelation.rule_id == rule.id)
            )
        )
        db.execute(delete(SceneRuleRelation).where(SceneRuleRelation.rule_id == rule.id))
        if scene_ids:
            db.execute(
                update(ReviewScene)
                .where(ReviewScene.id.in_(scene_ids))
                .values(update_time=utc_now())
            )
        db.delete(rule)
        db.commit()

    @staticmethod
    def get_rule(db: Session, rule_id: int) -> ReviewRule:
        rule = db.get(ReviewRule, rule_id)
        if not rule:
            raise RuleNotFoundError("审查规则不存在。")
        return rule

    @staticmethod
    def _make_rule_id() -> str:
        return f"R{uuid4().hex[:8].upper()}"
