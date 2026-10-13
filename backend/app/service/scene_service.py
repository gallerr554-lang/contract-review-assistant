from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.rule import ReviewRule
from app.core.time import utc_now
from app.models.scene import ReviewScene, SceneRuleRelation
from app.schemas.configuration import SceneCreateRequest, SceneUpdateRequest


class SceneNotFoundError(LookupError):
    pass


class SceneValidationError(ValueError):
    pass


class SceneService:
    def list_scenes(
        self,
        db: Session,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[tuple[ReviewScene, list[ReviewRule]]]:
        statement = select(ReviewScene)
        if keyword:
            statement = statement.where(ReviewScene.scene_name.ilike(f"%{keyword.strip()}%"))
        if enabled is not None:
            statement = statement.where(ReviewScene.status == enabled)
        scenes = list(
            db.scalars(statement.order_by(ReviewScene.display_order, ReviewScene.id))
        )
        return [(scene, self.get_scene_rules(db, scene.id)) for scene in scenes]

    def list_available(self, db: Session) -> list[ReviewScene]:
        statement = (
            select(ReviewScene)
            .join(SceneRuleRelation, SceneRuleRelation.scene_id == ReviewScene.id)
            .join(ReviewRule, ReviewRule.id == SceneRuleRelation.rule_id)
            .where(ReviewScene.status.is_(True), ReviewRule.status.is_(True))
            .group_by(ReviewScene.id)
            .having(func.count(ReviewRule.id) > 0)
            .order_by(ReviewScene.display_order, ReviewScene.id)
        )
        return list(db.scalars(statement))

    def create_scene(
        self, db: Session, request: SceneCreateRequest
    ) -> tuple[ReviewScene, list[ReviewRule]]:
        self._ensure_unique_name(db, request.scene_name, request.business_type)
        rules = self._load_rules(db, request.rule_ids)
        self._ensure_usable_when_enabled(request.status, rules)
        data = request.model_dump(exclude={"rule_ids"})
        scene = ReviewScene(**data)
        db.add(scene)
        db.flush()
        self._replace_relations(db, scene.id, request.rule_ids)
        db.commit()
        db.refresh(scene)
        return scene, rules

    def update_scene(
        self, db: Session, scene_id: int, request: SceneUpdateRequest
    ) -> tuple[ReviewScene, list[ReviewRule]]:
        scene = self.get_scene(db, scene_id)
        self._ensure_unique_name(db, request.scene_name, request.business_type, scene.id)
        rules = self._load_rules(db, request.rule_ids)
        self._ensure_usable_when_enabled(request.status, rules)
        for field, value in request.model_dump(exclude={"rule_ids"}).items():
            setattr(scene, field, value)
        scene.update_time = utc_now()
        self._replace_relations(db, scene.id, request.rule_ids)
        db.commit()
        db.refresh(scene)
        return scene, rules

    def set_status(
        self, db: Session, scene_id: int, enabled: bool
    ) -> tuple[ReviewScene, list[ReviewRule]]:
        scene = self.get_scene(db, scene_id)
        rules = self.get_scene_rules(db, scene.id)
        self._ensure_usable_when_enabled(enabled, rules)
        scene.status = enabled
        scene.update_time = utc_now()
        db.commit()
        db.refresh(scene)
        return scene, rules

    def delete_scene(self, db: Session, scene_id: int) -> None:
        scene = self.get_scene(db, scene_id)
        db.execute(delete(SceneRuleRelation).where(SceneRuleRelation.scene_id == scene.id))
        db.delete(scene)
        db.commit()

    @staticmethod
    def get_scene(db: Session, scene_id: int) -> ReviewScene:
        scene = db.get(ReviewScene, scene_id)
        if not scene:
            raise SceneNotFoundError("审查场景不存在。")
        return scene

    @staticmethod
    def get_scene_rules(
        db: Session, scene_id: int, only_enabled: bool = False
    ) -> list[ReviewRule]:
        statement = (
            select(ReviewRule)
            .join(SceneRuleRelation, SceneRuleRelation.rule_id == ReviewRule.id)
            .where(SceneRuleRelation.scene_id == scene_id)
        )
        if only_enabled:
            statement = statement.where(ReviewRule.status.is_(True))
        return list(db.scalars(statement.order_by(ReviewRule.rule_id)))

    @staticmethod
    def build_snapshot(scene: ReviewScene, rules: list[ReviewRule]) -> dict:
        return {
            "id": scene.id,
            "scene_name": scene.scene_name,
            "description": scene.description,
            "system_prompt": scene.system_prompt,
            "display_order": scene.display_order,
            "rules": [
                {
                    "id": rule.id,
                    "rule_id": rule.rule_id,
                    "rule_name": rule.rule_name,
                    "rule_type": rule.rule_type,
                    "risk_level": rule.risk_level,
                    "description": rule.description,
                    "review_requirement": rule.review_requirement,
                }
                for rule in rules
            ],
        }

    @staticmethod
    def _load_rules(db: Session, rule_ids: list[int]) -> list[ReviewRule]:
        unique_ids = list(dict.fromkeys(rule_ids))
        rules = list(db.scalars(select(ReviewRule).where(ReviewRule.id.in_(unique_ids))))
        if len(rules) != len(unique_ids):
            raise SceneValidationError("部分关联规则不存在，请刷新后重新选择。")
        rules_by_id = {rule.id: rule for rule in rules}
        return [rules_by_id[rule_id] for rule_id in unique_ids]

    @staticmethod
    def _ensure_usable_when_enabled(enabled: bool, rules: list[ReviewRule]) -> None:
        if enabled and not any(rule.status for rule in rules):
            raise SceneValidationError("启用场景至少需要关联 1 条已启用的审查规则。")

    @staticmethod
    def _replace_relations(db: Session, scene_id: int, rule_ids: list[int]) -> None:
        db.execute(delete(SceneRuleRelation).where(SceneRuleRelation.scene_id == scene_id))
        db.add_all(
            SceneRuleRelation(scene_id=scene_id, rule_id=rule_id)
            for rule_id in dict.fromkeys(rule_ids)
        )

    @staticmethod
    def _ensure_unique_name(
        db: Session,
        scene_name: str,
        business_type: str,
        current_id: int | None = None,
    ) -> None:
        statement = select(ReviewScene.id).where(
            ReviewScene.scene_name == scene_name.strip(),
            ReviewScene.business_type == business_type,
        )
        if current_id is not None:
            statement = statement.where(ReviewScene.id != current_id)
        if db.scalar(statement):
            raise SceneValidationError("同一业务分类下已存在同名场景。")
