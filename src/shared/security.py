"""RS256, bcrypt, Fernet (AES-128-CBC + HMAC-SHA256) and independent HMAC."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import re
import uuid
from pathlib import Path

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from shared.settings import ConfigurationError, Settings, secret

ACCESS_TOKEN_MINUTES = 15
JWT_ISSUER = "passanorte"
JWT_ALGORITHM = "RS256"


def verification_keys() -> dict[str, bytes]:
    directory = os.environ.get("JWT_PUBLIC_KEYS_DIR", "")
    if not directory:
        raise ConfigurationError("Missing JWT_PUBLIC_KEYS_DIR")
    keys = {}
    try:
        for path in Path(directory).glob("*.pem"):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", path.stem):
                raise ValueError
            pem = path.read_bytes()
            key = serialization.load_pem_public_key(pem)
            if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048:
                raise ValueError
            keys[path.stem] = pem
        if not keys:
            raise ValueError
    except (OSError, ValueError):
        raise ConfigurationError("Invalid RSA public key directory (minimum 2048 bits)") from None
    return keys


def signing_key() -> tuple[str, bytes]:
    kid = os.environ.get("JWT_ACTIVE_KID", "")
    pem = secret("JWT_PRIVATE_KEY").encode()
    try:
        key = serialization.load_pem_private_key(pem, password=None)
        public = verification_keys().get(kid)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048 or public is None:
            raise ValueError
        if key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ) != public:
            raise ValueError
    except (ValueError, TypeError):
        raise ConfigurationError("JWT_PRIVATE_KEY must match JWT_ACTIVE_KID public key") from None
    return kid, pem


def _create(user_id: str, role: str, token_type: str) -> tuple[str, int]:
    settings = Settings.load()
    seconds = settings.access_token_minutes * 60 if token_type == "access" else settings.refresh_token_days * 86400
    now = dt.datetime.now(dt.UTC)
    kid, key = signing_key()
    claims = {
        "sub": user_id, "role": role, "type": token_type,
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
        "iat": now, "exp": now + dt.timedelta(seconds=seconds), "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, key, algorithm=JWT_ALGORITHM, headers={"kid": kid}), seconds


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    return _create(user_id, role, "access")


def create_refresh_token(user_id: str, role: str) -> str:
    return _create(user_id, role, "refresh")[0]


def decode_token(token: str, expected_type: str = "access") -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    key = verification_keys().get(kid) if isinstance(kid, str) else None
    if header.get("alg") != JWT_ALGORITHM or key is None:
        raise jwt.InvalidTokenError("Unknown signing key or algorithm")
    settings = Settings.load()
    claims = jwt.decode(
        token, key, algorithms=[JWT_ALGORITHM], issuer=settings.jwt_issuer, audience=settings.jwt_audience,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "type", "role", "jti"], "strict_aud": True},
    )
    if claims["type"] != expected_type or claims["role"] not in ("admin", "supplier", "tourist") or any(
        not isinstance(claims[name], str) or not claims[name] for name in ("sub", "role", "jti")
    ):
        raise jwt.InvalidTokenError("Invalid token claims")
    if any(type(claims[name]) is not int for name in ("exp", "iat")):
        raise jwt.InvalidTokenError("Numeric dates required")
    if claims["exp"] <= claims["iat"]:
        raise jwt.InvalidTokenError("Invalid token lifetime")
    return claims


def validate_password(password: str) -> str:
    if not 8 <= len(password.encode("utf-8")) <= 72:
        raise ValueError("Password must contain 8 to 72 UTF-8 bytes")
    return password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(validate_password(password).encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode()) > 72:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def encryption() -> MultiFernet:
    try:
        keys = secret("PII_ENCRYPTION_KEY").split(",")
        return MultiFernet([Fernet(key.strip().encode()) for key in keys])
    except (ValueError, TypeError):
        raise ConfigurationError("PII_ENCRYPTION_KEY must contain valid Fernet keys") from None


def encrypt_pii(value: str) -> str:
    return encryption().encrypt(value.encode()).decode()


def decrypt_pii(value: str) -> str:
    try:
        return encryption().decrypt(value.encode()).decode()
    except InvalidToken:
        raise ValueError("Cannot decrypt sensitive data") from None


def pii_uniqueness_hash(value: str) -> str:
    key = secret("PII_HMAC_KEY").encode()
    if len(key) < 32:
        raise ConfigurationError("PII_HMAC_KEY must have at least 32 bytes")
    return hmac.new(key, value.encode().lower(), hashlib.sha256).hexdigest()
