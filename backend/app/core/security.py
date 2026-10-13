import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretConfigurationError(ValueError):
    pass


class SecretDecryptionError(ValueError):
    pass


class SecretCipher:
    def __init__(self, encryption_key: str | None = None) -> None:
        self.encryption_key = encryption_key or settings.model_config_encryption_key

    @property
    def configured(self) -> bool:
        return bool(self.encryption_key)

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError("模型 API Key 无法解密，请重新填写。") from exc

    def _fernet(self) -> Fernet:
        if not self.encryption_key:
            raise SecretConfigurationError(
                "未配置 MODEL_CONFIG_ENCRYPTION_KEY，无法安全保存模型 API Key。"
            )
        try:
            return Fernet(self.encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise SecretConfigurationError(
                "MODEL_CONFIG_ENCRYPTION_KEY 格式无效，请使用 Fernet.generate_key() 生成。"
            ) from exc


PASSWORD_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_value, digest_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_value.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
