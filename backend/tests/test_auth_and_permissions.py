from collections.abc import Generator

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.api.model import model_config_service
from app.core.dependencies import get_current_user, require_admin
from app.core.config import settings
from app.core.security import SecretCipher, verify_password
from app.database.session import get_db
from app.main import app
from app.models import Base
from app.models.review import ReviewTask
from app.models.user import AuthCaptcha, User
from app.schemas.auth import AuthCredentials
from app.service.auth_service import AuthService, AuthValidationError
from app.service.captcha_service import captcha_png_data_uri
from app.service.model_service import ModelService


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def captcha_request(db: Session, email: str, password: str, code: str = "1234") -> AuthCredentials:
    service = AuthService()
    captcha_id = "a" * 36 if email.startswith("first") else "b" * 36
    db.add(
        AuthCaptcha(
            id=captcha_id,
            code_hash=service._captcha_hash(captcha_id, code),
            expires_at=service.now().replace(year=service.now().year + 1),
            used=False,
        )
    )
    db.commit()
    return AuthCredentials(
        email=email,
        password=password,
        captcha_id=captcha_id,
        captcha_code=code,
    )


def test_register_login_and_captcha_is_single_use(db: Session) -> None:
    service = AuthService()
    register_request = captcha_request(db, "first@example.com", "Password123")
    user, token, expires_at = service.register(db, register_request)

    assert user.role == "user"
    assert token
    assert expires_at > service.now()
    assert get_current_user(db, f"Bearer {token}").id == user.id
    with pytest.raises(AuthValidationError, match="失效"):
        service.register(db, register_request)

    login_request = captcha_request(db, "login@example.com", "Password123")
    login_request.email = user.email
    logged_in, login_token, _ = service.login(db, login_request)
    assert logged_in.id == user.id
    assert get_current_user(db, f"Bearer {login_token}").email == user.email


def test_admin_dependency_rejects_normal_user(db: Session) -> None:
    service = AuthService()
    user, _, _ = service.register(
        db, captcha_request(db, "first-admin-check@example.com", "Password123")
    )
    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)
    assert exc_info.value.status_code == 403
    user.role = "admin"
    assert require_admin(user).id == user.id


def test_initial_admin_promotes_existing_user_and_updates_password(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = AuthService()
    user, _, _ = service.register(
        db, captcha_request(db, "first-bootstrap@example.com", "OldPassword123")
    )
    monkeypatch.setattr(settings, "initial_admin_email", user.email)
    monkeypatch.setattr(settings, "initial_admin_password", "NewPassword456")

    admin = service.ensure_initial_admin(db)

    assert admin is not None
    assert admin.role == "admin"
    assert verify_password("NewPassword456", admin.password_hash)


def test_captcha_is_png_not_plain_text() -> None:
    image = captcha_png_data_uri("1234")
    assert image.startswith("data:image/png;base64,iVBOR")
    assert "1234" not in image


def test_http_routes_enforce_role_ownership_and_admin_model_configuration() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    encryption_key = Fernet.generate_key().decode("ascii")
    original_cipher = model_config_service.cipher
    model_config_service.cipher = SecretCipher(encryption_key)
    client = TestClient(app)

    def register_user(email: str, captcha_id: str) -> tuple[int, str]:
        db = testing_session()
        service = AuthService()
        db.add(
            AuthCaptcha(
                id=captcha_id,
                code_hash=service._captcha_hash(captcha_id, "1234"),
                expires_at=service.now().replace(year=service.now().year + 1),
                used=False,
            )
        )
        db.commit()
        db.close()
        response = client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "Password123",
                "captcha_id": captcha_id,
                "captcha_code": "1234",
            },
        )
        assert response.status_code == 201
        payload = response.json()
        return payload["user"]["id"], payload["access_token"]

    try:
        first_id, first_token = register_user("first-http@example.com", "1" * 36)
        second_id, second_token = register_user("second-http@example.com", "2" * 36)
        db = testing_session()
        first_user = db.get(User, first_id)
        first_user.role = "admin"
        db.commit()
        db.close()
        first_headers = {"Authorization": f"Bearer {first_token}"}
        second_headers = {"Authorization": f"Bearer {second_token}"}

        assert client.get("/api/rules", headers=second_headers).status_code == 403
        assert client.get("/api/scenes", headers=second_headers).status_code == 403
        assert client.get("/api/models", headers=second_headers).status_code == 403

        db = testing_session()
        other_task = ReviewTask(
            task_no="CR-OTHER-USER",
            user_id=second_id,
            upload_id="a" * 36,
            contract_name="隔离测试合同.txt",
            contract_text="合同正文",
            attachment_names=[],
            attachment_texts=[],
            scene_name="测试场景",
            scene_snapshot={"rules": []},
            model_snapshot={},
            document_pages=[],
            document_meta={},
            scale="标准",
            position="甲方",
            status="SUCCESS",
            progress=100,
            current_step=5,
            current_message="完成",
        )
        db.add(other_task)
        db.commit()
        other_task_id = other_task.id
        db.close()
        assert (
            client.get(f"/api/review/{other_task_id}/status", headers=first_headers).status_code
            == 404
        )

        response = client.post(
            "/api/models",
            headers=first_headers,
            json={
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "api_base": "https://api.deepseek.com",
                "api_key": "system-deepseek-secret",
                "temperature": 0.2,
                "max_tokens": 2048,
                "status": True,
            },
        )
        assert response.status_code == 201
        model_id = response.json()["id"]
        assert "system-deepseek-secret" not in response.text
        assert client.post("/api/models", headers=second_headers, json={}).status_code == 403
        assert (
            client.post(f"/api/models/{model_id}/test", headers=second_headers).status_code
            == 403
        )

        original_test_connection = ModelService.test_connection
        ModelService.test_connection = lambda self: {
            "success": True,
            "http_status": 200,
            "message": "连接成功",
        }
        try:
            test_response = client.post(
                f"/api/models/{model_id}/test", headers=first_headers
            )
        finally:
            ModelService.test_connection = original_test_connection
        assert test_response.status_code == 200
        assert test_response.json()["model_name"] == "deepseek-chat"
        assert test_response.json()["http_status"] == 200
        assert "system-deepseek-secret" not in test_response.text

        response = client.get("/api/models", headers=first_headers)
        assert response.status_code == 200
        assert [item["model_name"] for item in response.json()] == ["deepseek-chat"]
        assert all(
            "api_key" not in item and "api_key_encrypted" not in item
            for item in response.json()
        )
        assert first_id != second_id
    finally:
        app.dependency_overrides.clear()
        model_config_service.cipher = original_cipher
