from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from jose import JWTError, jwt

from app.config import get_settings

_HASH_NAME = "sha256"
_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = encoded.split("$", maxsplit=3)
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str) -> tuple[str, int]:
    settings = get_settings()
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY must be configured before issuing access tokens")
    expires_in = settings.access_token_expire_minutes * 60
    expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    encoded = jwt.encode({"sub": subject, "exp": expires}, settings.secret_key, algorithm="HS256")
    return encoded, expires_in


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    if not settings.secret_key:
        return None
    try:
        subject = jwt.decode(token, settings.secret_key, algorithms=["HS256"]).get("sub")
    except JWTError:
        return None
    return subject if isinstance(subject, str) else None
