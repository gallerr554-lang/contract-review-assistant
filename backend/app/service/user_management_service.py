from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.time import utc_now
from app.models.review import ReviewTask
from app.models.user import User, UserOperationLog, UserSession


class ManagedUserNotFoundError(LookupError):
    pass


class ManagedUserConflictError(ValueError):
    pass


class UserManagementService:
    def list_users(
        self,
        db: Session,
        keyword: str | None = None,
        role: str | None = None,
        enabled: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[tuple[User, int]], int]:
        filters = []
        if keyword:
            filters.append(User.email.ilike(f"%{keyword.strip()}%"))
        if role:
            filters.append(User.role == role)
        if enabled is not None:
            filters.append(User.status == enabled)

        total = int(db.scalar(select(func.count()).select_from(User).where(*filters)) or 0)
        task_counts = (
            select(
                ReviewTask.user_id.label("user_id"),
                func.count(ReviewTask.id).label("task_count"),
            )
            .where(ReviewTask.user_id.is_not(None))
            .group_by(ReviewTask.user_id)
            .subquery()
        )
        statement = (
            select(User, func.coalesce(task_counts.c.task_count, 0))
            .outerjoin(task_counts, task_counts.c.user_id == User.id)
            .where(*filters)
            .order_by(User.create_time.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [(user, int(task_count)) for user, task_count in db.execute(statement)], total

    def get_user_with_task_count(self, db: Session, user_id: int) -> tuple[User, int]:
        user = db.get(User, user_id)
        if not user:
            raise ManagedUserNotFoundError("用户不存在。")
        task_count = int(
            db.scalar(
                select(func.count()).select_from(ReviewTask).where(ReviewTask.user_id == user.id)
            )
            or 0
        )
        return user, task_count

    def set_status(
        self, db: Session, operator_user_id: int, target_user_id: int, enabled: bool
    ) -> tuple[User, int]:
        target = self._locked_user(db, target_user_id)
        self._ensure_not_self(operator_user_id, target.id, "不能停用或启用自己的账号。")
        if target.status == enabled:
            return self.get_user_with_task_count(db, target.id)
        if not enabled and target.role == "admin" and target.status:
            self._ensure_another_active_admin(db, target.id)

        before = "enabled" if target.status else "disabled"
        target.status = enabled
        if not enabled:
            db.execute(delete(UserSession).where(UserSession.user_id == target.id))
        self._add_log(
            db,
            operator_user_id,
            target.id,
            "status_change",
            before,
            "enabled" if enabled else "disabled",
        )
        db.commit()
        db.refresh(target)
        return self.get_user_with_task_count(db, target.id)

    def set_role(
        self, db: Session, operator_user_id: int, target_user_id: int, role: str
    ) -> tuple[User, int]:
        target = self._locked_user(db, target_user_id)
        self._ensure_not_self(operator_user_id, target.id, "不能修改自己的角色。")
        if target.role == role:
            return self.get_user_with_task_count(db, target.id)
        if target.role == "admin" and role == "user" and target.status:
            self._ensure_another_active_admin(db, target.id)

        before = target.role
        target.role = role
        self._add_log(db, operator_user_id, target.id, "role_change", before, role)
        db.commit()
        db.refresh(target)
        return self.get_user_with_task_count(db, target.id)

    def reset_password(
        self,
        db: Session,
        operator_user_id: int,
        target_user_id: int,
        new_password: str,
    ) -> tuple[User, int]:
        target = self._locked_user(db, target_user_id)
        self._ensure_not_self(operator_user_id, target.id, "不能重置自己的密码。")
        target.password_hash = hash_password(new_password)
        db.execute(delete(UserSession).where(UserSession.user_id == target.id))
        self._add_log(
            db,
            operator_user_id,
            target.id,
            "password_reset",
            None,
            "password_hash_updated",
        )
        db.commit()
        db.refresh(target)
        return self.get_user_with_task_count(db, target.id)

    @staticmethod
    def _locked_user(db: Session, user_id: int) -> User:
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        if not user:
            raise ManagedUserNotFoundError("用户不存在。")
        return user

    @staticmethod
    def _ensure_not_self(operator_user_id: int, target_user_id: int, message: str) -> None:
        if operator_user_id == target_user_id:
            raise ManagedUserConflictError(message)

    @staticmethod
    def _ensure_another_active_admin(db: Session, target_user_id: int) -> None:
        active_admin_ids = list(
            db.scalars(
                select(User.id)
                .where(User.role == "admin", User.status.is_(True))
                .order_by(User.id)
                .with_for_update()
            )
        )
        if target_user_id in active_admin_ids and len(active_admin_ids) <= 1:
            raise ManagedUserConflictError("系统必须至少保留一个启用状态的管理员。")

    @staticmethod
    def _add_log(
        db: Session,
        operator_user_id: int,
        target_user_id: int,
        action: str,
        before_value: str | None,
        after_value: str | None,
    ) -> None:
        db.add(
            UserOperationLog(
                operator_user_id=operator_user_id,
                target_user_id=target_user_id,
                action=action,
                before_value=before_value,
                after_value=after_value,
                create_time=utc_now(),
            )
        )
