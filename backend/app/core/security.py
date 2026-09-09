"""Hash de senha e emissao/validacao de JWT.

Usamos `bcrypt` direto (sem passlib, que esta sem manutencao e quebra com as
versoes novas do bcrypt). O segredo passa por SHA-256 + base64 antes do bcrypt
porque o bcrypt trunca em 72 bytes - sem o pre-hash, duas senhas longas com o
mesmo prefixo seriam equivalentes.
"""

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def _prepare(plain: str) -> bytes:
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(member_id: UUID, family_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(member_id),
        "fam": str(family_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
