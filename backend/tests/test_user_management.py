from collections.abc import Generator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user, require_admin
from app.core.security import hash_password, verify_password
from app.database.session import get_db
from app.main import app
from app.models import Base
from app.models.review import ReviewTask
from app.models.user import User, UserOperationLog, UserSession
from app.service.auth_service import AuthService
from app.service.user_management_service import (
    ManagedUserConflictError,
    UserManagementService,
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


def create_user(
    db: Session,
    email: str,
    role: str = "user",
    status: bool = True,
) -> tuple[User, str]:
    user = User(
        email=email,
        password_hash=hash_password("Password123"),
        role=role,
        status=status,
    )
    db.add(user)
    db.flush()
    token, _ = AuthService()._create_session(db, user)
    db.commit()
    db.refresh(user)
    return user, token


def add_task(db: Session, user_id: int, task_no: str) -> ReviewTask:
    task = ReviewTask(
        task_no=task_no,
        user_id=user_id,
        upload_id="a" * 36,
        contract_name="用户管理测试合同.txt",
        contract_text="合同正文",
        attachment_names=[],
        attachment_texts=[],
        scene_name="测试场景",
        scene_snapshot={"rules": []},
        model_snapshot={},
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
    db.commit()
    return task


def test_user_query_filters_pagination_and_task_count(db: Session) -> None:
    service = UserManagementService()
    admin, _ = create_user(db, "admin@example.com", role="admin")
    user, _ = create_user(db, "buyer@example.com")
    create_user(db, "disabled@example.com", status=False)
    add_task(db, user.id, "CR-USER-MANAGEMENT-1")
    add_task(db, user.id, "CR-USER-MANAGEMENT-2")

    items, total = service.list_users(
        db, keyword="buyer", role="user", enabled=True, page=1, page_size=10
    )

    assert total == 1
    assert [(item.email, count) for item, count in items] == [(user.email, 2)]
    assert admin.id != user.id


def test_disabling_user_revokes_sessions_and_preserves_tasks(db: Session) -> None:
    service = UserManagementService()
    admin, _ = create_user(db, "admin@example.com", role="admin")
    user, token = create_user(db, "user@example.com")
    task = add_task(db, user.id, "CR-USER-DISABLE")

    updated, task_count = service.set_status(db, admin.id, user.id, False)

    assert updated.status is False
    assert task_count == 1
    assert db.get(ReviewTask, task.id) is not None
    assert db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)) == 0
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db, f"Bearer {token}")
    assert exc_info.value.status_code == 401
    log = db.scalar(select(UserOperationLog).where(UserOperationLog.target_user_id == user.id))
    assert log is not None
    assert (log.action, log.before_value, log.after_value) == (
        "status_change",
        "enabled",
        "disabled",
    )


def test_role_changes_apply_to_existing_session_and_self_changes_are_blocked(
    db: Session,
) -> None:
    service = UserManagementService()
    admin, _ = create_user(db, "admin@example.com", role="admin")
    user, token = create_user(db, "user@example.com")

    promoted, _ = service.set_role(db, admin.id, user.id, "admin")
    assert promoted.role == "admin"
    assert require_admin(get_current_user(db, f"Bearer {token}")).id == user.id

    demoted, _ = service.set_role(db, admin.id, user.id, "user")
    assert demoted.role == "user"
    with pytest.raises(HTTPException) as exc_info:
        require_admin(get_current_user(db, f"Bearer {token}"))
    assert exc_info.value.status_code == 403

    with pytest.raises(ManagedUserConflictError, match="自己的角色"):
        service.set_role(db, admin.id, admin.id, "user")
    with pytest.raises(ManagedUserConflictError, match="自己的账号"):
        service.set_status(db, admin.id, admin.id, False)
    with pytest.raises(ManagedUserConflictError, match="自己的密码"):
        service.reset_password(db, admin.id, admin.id, "NewPassword456")


def test_last_active_admin_cannot_be_removed(db: Session) -> None:
    service = UserManagementService()
    inactive_operator, _ = create_user(
        db, "inactive-admin@example.com", role="admin", status=False
    )
    last_admin, _ = create_user(db, "last-admin@example.com", role="admin")

    with pytest.raises(ManagedUserConflictError, match="至少保留"):
        service.set_role(db, inactive_operator.id, last_admin.id, "user")
    with pytest.raises(ManagedUserConflictError, match="至少保留"):
        service.set_status(db, inactive_operator.id, last_admin.id, False)


def test_password_reset_hashes_password_revokes_sessions_and_never_logs_plaintext(
    db: Session,
) -> None:
    service = UserManagementService()
    admin, _ = create_user(db, "admin@example.com", role="admin")
    user, token = create_user(db, "user@example.com")
    old_hash = user.password_hash

    updated, _ = service.reset_password(db, admin.id, user.id, "NewPassword456")

    assert updated.password_hash != old_hash
    assert "NewPassword456" not in updated.password_hash
    assert verify_password("NewPassword456", updated.password_hash)
    assert db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)) == 0
    with pytest.raises(HTTPException):
        get_current_user(db, f"Bearer {token}")
    log = db.scalar(
        select(UserOperationLog).where(UserOperationLog.action == "password_reset")
    )
    assert log is not None
    assert "NewPassword456" not in f"{log.before_value}{log.after_value}"


def test_user_management_http_permissions_confirmation_and_session_invalidation() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    seed = testing_session()
    admin, admin_token = create_user(seed, "admin-http@example.com", role="admin")
    admin_id = admin.id
    user, user_token = create_user(seed, "user-http@example.com")
    user_id = user.id
    seed.close()
    client = TestClient(app)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}

    try:
        assert client.get("/api/users", headers=user_headers).status_code == 403
        response = client.get("/api/users", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert "password_hash" not in response.text

        assert (
                client.patch(
                    f"/api/users/{user_id}/status",
                headers=admin_headers,
                json={"status": False},
            ).status_code
            == 422
        )
        assert (
            client.patch(
                f"/api/users/{admin_id}/role",
                headers=admin_headers,
                json={"role": "user", "confirmed": True},
            ).status_code
            == 409
        )
        changed = client.patch(
            f"/api/users/{user_id}/status",
            headers=admin_headers,
            json={"status": False, "confirmed": True},
        )
        assert changed.status_code == 200
        assert changed.json()["status"] is False
        assert client.get("/api/auth/me", headers=user_headers).status_code == 401
    finally:
        app.dependency_overrides.clear()
