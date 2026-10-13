import hashlib
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, utc_now
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models.review import ReviewRiskFeedback, ReviewTask
from app.models.user import AuthCaptcha, User, UserSession
from app.schemas.auth import AuthCredentials
from app.service.captcha_service import captcha_png_data_uri, make_numeric_code
from app.service.file_service import FileService


class AuthValidationError(ValueError):
    pass


class AuthConflictError(ValueError):
    pass


class AuthService:
    @staticmethod
    def now() -> datetime:
        return utc_now()

    def create_captcha(self, db: Session) -> tuple[AuthCaptcha, str]:
        now = self.now()
        db.execute(delete(AuthCaptcha).where(AuthCaptcha.expires_at < now))
        code = make_numeric_code()
        captcha_id = str(uuid4())
        captcha = AuthCaptcha(
            id=captcha_id,
            code_hash=self._captcha_hash(captcha_id, code),
            expires_at=now + timedelta(minutes=settings.captcha_expire_minutes),
            used=False,
            create_time=now,
        )
        db.add(captcha)
        db.commit()
        return captcha, captcha_png_data_uri(code)

    def register(self, db: Session, request: AuthCredentials) -> tuple[User, str, datetime]:
        self._consume_captcha(db, request.captcha_id, request.captcha_code)
        email = request.email.lower()
        if db.scalar(select(User.id).where(User.email == email)):
            raise AuthConflictError("该邮箱已注册。")
        user = User(
            email=email,
            password_hash=hash_password(request.password),
            role="user",
            status=True,
            create_time=self.now(),
        )
        db.add(user)
        db.flush()
        token, expires_at = self._create_session(db, user)
        db.commit()
        db.refresh(user)
        return user, token, expires_at

    def login(self, db: Session, request: AuthCredentials) -> tuple[User, str, datetime]:
        self._consume_captcha(db, request.captcha_id, request.captcha_code)
        user = db.scalar(select(User).where(User.email == request.email.lower()))
        if not user or not verify_password(request.password, user.password_hash):
            raise AuthValidationError("邮箱或密码错误。")
        if not user.status:
            raise AuthValidationError("当前账号已停用。")
        user.last_login_time = self.now()
        token, expires_at = self._create_session(db, user)
        db.commit()
        db.refresh(user)
        return user, token, expires_at

    def logout(self, db: Session, token: str) -> None:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        db.commit()

    def ensure_initial_admin(self, db: Session) -> User | None:
        email = (settings.initial_admin_email or "").strip().lower()
        password = settings.initial_admin_password or ""
        if not email or not password:
            return None
        if len(password) < 8 or not any(char.isalpha() for char in password) or not any(
            char.isdigit() for char in password
        ):
            raise AuthValidationError("INITIAL_ADMIN_PASSWORD 至少 8 位且必须包含字母和数字。")
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                email=email,
                password_hash=hash_password(password),
                role="admin",
                status=True,
                create_time=self.now(),
            )
            db.add(user)
            db.flush()
        else:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.status = True
        legacy_tasks = list(db.scalars(select(ReviewTask).where(ReviewTask.user_id.is_(None))))
        file_service = FileService()
        for task in legacy_tasks:
            file_service.claim_manifest(task.upload_id, user.id)
        db.execute(update(ReviewTask).where(ReviewTask.user_id.is_(None)).values(user_id=user.id))
        db.execute(
            update(ReviewRiskFeedback)
            .where(ReviewRiskFeedback.user_id.is_(None))
            .values(user_id=user.id)
        )
        db.commit()
        db.refresh(user)
        return user

    def _consume_captcha(self, db: Session, captcha_id: str, code: str) -> None:
        captcha = db.scalar(
            select(AuthCaptcha)
            .where(AuthCaptcha.id == captcha_id)
            .with_for_update()
        )
        now = self.now()
        if not captcha or captcha.used or as_utc(captcha.expires_at) < now:
            raise AuthValidationError("验证码已失效，请刷新后重试。")
        captcha.used = True
        db.flush()
        if captcha.code_hash != self._captcha_hash(captcha_id, code):
            db.commit()
            raise AuthValidationError("验证码错误，请刷新后重试。")

    def _create_session(self, db: Session, user: User) -> tuple[str, datetime]:
        token = new_session_token()
        expires_at = self.now() + timedelta(hours=settings.auth_session_hours)
        db.add(
            UserSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=expires_at,
                create_time=self.now(),
            )
        )
        return token, expires_at

    @staticmethod
    def _captcha_hash(captcha_id: str, code: str) -> str:
        return hashlib.sha256(f"{captcha_id}:{code}".encode("utf-8")).hexdigest()
