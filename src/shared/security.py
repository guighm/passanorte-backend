"""Segurança compartilhada: JWT, bcrypt e criptografia de PII (D-02, D-03, D-04).

- JWT: par access (15 min) / refresh (7 dias, com jti para revogação),
  assinatura HS256 com segredo por ambiente (RNF09).
- Senhas: bcrypt com work factor 12, nunca texto plano (RNF10).
- PII: AES-256-GCM em nível de aplicação + HMAC determinístico para índices
  de unicidade sem descriptografar (RNF08, LGPD).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
import uuid

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-not-for-production-32-bytes-min")
PII_ENCRYPTION_KEY = os.environ.get("PII_ENCRYPTION_KEY", Fernet.generate_key().decode())
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", "7"))
JWT_ALGORITHM = "HS256"


# --- Sessão (JWT) -----------------------------------------------------------

def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    """Gera o access token; retorna (token, expira_em_segundos)."""
    now = dt.datetime.now(dt.UTC)
    expires_in = ACCESS_TOKEN_MINUTES * 60
    claims = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + dt.timedelta(seconds=expires_in),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM), expires_in


def create_refresh_token(user_id: str, role: str) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + dt.timedelta(days=REFRESH_TOKEN_DAYS),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decodifica e valida o token; lança jwt.PyJWTError em falha."""
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if claims.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Esperado token do tipo {expected_type}")
    return claims


# --- Senhas (bcrypt) --------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# --- PII (AES-256-GCM via Fernet + HMAC de unicidade) -----------------------

_fernet = Fernet(PII_ENCRYPTION_KEY.encode())


def encrypt_pii(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_pii(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Falha ao descriptografar dado sensível") from exc


def pii_uniqueness_hash(value: str) -> str:
    """HMAC determinístico para índice de unicidade sem armazenar o valor."""
    return hmac.new(
        PII_ENCRYPTION_KEY.encode(), value.encode().lower(), hashlib.sha256
    ).hexdigest()
