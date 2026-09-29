import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]
LIFETIMES: dict[TokenType, timedelta] = {
    "access": timedelta(minutes=30),
    "refresh": timedelta(days=7),
}

password_hash = PasswordHash.recommended()  # Argon2


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_token(user_id: uuid.UUID, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + LIFETIMES[token_type],
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, token_type: TokenType) -> uuid.UUID | None:
    """User id from a valid token of the expected type, else None."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != token_type:
        return None
    return uuid.UUID(payload["sub"])
