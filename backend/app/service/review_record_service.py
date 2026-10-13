from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.review import ReviewRisk, ReviewRiskFeedback, ReviewTask
from app.schemas.review import ReviewHistoryItem, RiskFeedbackCreateRequest


class ReviewRecordNotFoundError(LookupError):
    pass


class ReviewRecordValidationError(ValueError):
    pass


class ReviewRecordService:
    def list_history(
        self,
        db: Session,
        user_id: int,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ReviewHistoryItem], int]:
        filters = [ReviewTask.user_id == user_id]
        if keyword:
            pattern = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    ReviewTask.contract_name.ilike(pattern),
                    ReviewTask.task_no.ilike(pattern),
                )
            )
        if status:
            filters.append(ReviewTask.status == status)

        total = int(
            db.scalar(select(func.count()).select_from(ReviewTask).where(*filters)) or 0
        )
        risk_stats = (
            select(
                ReviewRisk.task_id.label("task_id"),
                func.count(ReviewRisk.id).label("risk_total"),
                func.sum(case((ReviewRisk.risk_level == "high", 1), else_=0)).label(
                    "high_count"
                ),
                func.sum(case((ReviewRisk.risk_level == "medium", 1), else_=0)).label(
                    "medium_count"
                ),
                func.sum(case((ReviewRisk.risk_level == "low", 1), else_=0)).label(
                    "low_count"
                ),
            )
            .group_by(ReviewRisk.task_id)
            .subquery()
        )
        statement = (
            select(
                ReviewTask,
                func.coalesce(risk_stats.c.risk_total, 0),
                func.coalesce(risk_stats.c.high_count, 0),
                func.coalesce(risk_stats.c.medium_count, 0),
                func.coalesce(risk_stats.c.low_count, 0),
            )
            .outerjoin(risk_stats, risk_stats.c.task_id == ReviewTask.id)
            .where(*filters)
            .order_by(ReviewTask.create_time.desc(), ReviewTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            ReviewHistoryItem(
                id=task.id,
                task_no=task.task_no,
                contract_name=task.contract_name,
                scene_name=task.scene_name,
                scale=task.scale,
                position=task.position,
                status=task.status,
                risk_total=int(risk_total),
                high_risk_count=int(high_count),
                medium_risk_count=int(medium_count),
                low_risk_count=int(low_count),
                error_message=task.error_message,
                create_time=task.create_time,
            )
            for task, risk_total, high_count, medium_count, low_count in db.execute(
                statement
            )
        ]
        return items, total

    @staticmethod
    def create_feedback(
        db: Session,
        user_id: int,
        task_id: int,
        risk_id: int,
        request: RiskFeedbackCreateRequest,
    ) -> ReviewRiskFeedback:
        task = db.scalar(
            select(ReviewTask).where(ReviewTask.id == task_id, ReviewTask.user_id == user_id)
        )
        if not task:
            raise ReviewRecordNotFoundError("审查任务不存在。")
        if task.status != "SUCCESS":
            raise ReviewRecordValidationError("仅已完成任务可以提交风险反馈。")
        risk = db.scalar(
            select(ReviewRisk).where(
                ReviewRisk.id == risk_id, ReviewRisk.task_id == task_id
            )
        )
        if not risk:
            raise ReviewRecordNotFoundError("风险项不存在或不属于当前任务。")
        existing = db.scalar(
            select(ReviewRiskFeedback).where(
                ReviewRiskFeedback.task_id == task_id,
                ReviewRiskFeedback.risk_id == risk_id,
            )
        )
        if existing:
            return existing
        feedback = ReviewRiskFeedback(
            task_id=task_id,
            user_id=user_id,
            risk_id=risk_id,
            rule_id=risk.rule_id,
            content=request.content,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
