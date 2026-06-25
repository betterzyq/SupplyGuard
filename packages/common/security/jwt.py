"""JWT token utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from packages.common.config import Settings, get_settings


def create_access_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        **(claims or {}),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def verify_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    try:
        return decode_access_token(token, settings)
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
