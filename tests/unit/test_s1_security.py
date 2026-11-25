"""S1 acceptance: rejected claims, key overlap, sessions, bootstrap and config."""
import importlib.util
import time
from pathlib import Path

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from services.auth.app.api.session import login, logout, refresh
from services.auth.app.models.user import User, UserRole
from services.auth.app.schemas.auth_schemas import LoginRequest, RefreshRequest, TouristCreate
from shared import security
from shared.errors import ApiError
from shared.settings import ConfigurationError, Settings, validate_service


def signed(claims):
    kid, key = security.signing_key()
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


@pytest.mark.parametrize("claim", ["exp", "iat", "sub", "iss", "aud", "type", "role", "jti"])
def test_missing_claim_rejected(claim):
    claims = security.decode_token(security.create_access_token("u", "tourist")[0])
    del claims[claim]
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(signed(claims))


@pytest.mark.parametrize(("claim", "value"), [
    ("iss", "attacker"), ("aud", "other-api"), ("type", "refresh"),
    ("exp", int(time.time()) - 60), ("sub", ""), ("sub", 123), ("jti", ""),
])
def test_invalid_claim_rejected(claim, value):
    claims = security.decode_token(security.create_access_token("u", "tourist")[0])
    claims[claim] = value
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(signed(claims))


def test_hs256_cannot_use_public_key_as_secret():
    token = jwt.encode(
        {"sub": "u"}, "untrusted-test-key-with-at-least-32-bytes", algorithm="HS256", headers={"kid": "test"},
    )
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(token)


def test_key_overlap_and_retirement(tmp_path, monkeypatch):
    old_token = security.create_access_token("u", "tourist")[0]
    public = tmp_path / "public"
    public.mkdir()
    for kid, pem in security.verification_keys().items():
        (public / f"{kid}.pem").write_bytes(pem)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (public / "next.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    private = tmp_path / "private.key"
    private.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    monkeypatch.setenv("JWT_PUBLIC_KEYS_DIR", str(public))
    monkeypatch.setenv("JWT_PRIVATE_KEY_FILE", str(private))
    monkeypatch.setenv("JWT_ACTIVE_KID", "next")
    new_token = security.create_access_token("u", "tourist")[0]
    assert security.decode_token(old_token)["sub"] == "u"
    assert security.decode_token(new_token)["sub"] == "u"
    (public / "test.pem").unlink()
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(old_token)
    assert security.decode_token(new_token)["sub"] == "u"


def test_verifier_does_not_need_private_key(monkeypatch):
    token = security.create_access_token("u", "tourist")[0]
    monkeypatch.delenv("JWT_PRIVATE_KEY_FILE")
    assert security.decode_token(token)["sub"] == "u"
    validate_service("catalog")
    with pytest.raises(ConfigurationError):
        validate_service("auth")


def test_pii_rotation_does_not_change_uniqueness(monkeypatch):
    old = security.secret("PII_ENCRYPTION_KEY")
    ciphertext = security.encrypt_pii("document")
    digest = security.pii_uniqueness_hash("document")
    monkeypatch.setenv("PII_ENCRYPTION_KEY", Fernet.generate_key().decode() + "," + old)
    assert security.decrypt_pii(ciphertext) == "document"
    assert security.pii_uniqueness_hash("document") == digest


def test_configuration_missing_or_conflicting_secret_is_safe(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ConfigurationError, match="Missing DATABASE_URL"):
        Settings.load()
    monkeypatch.setenv("DATABASE_URL", "sensitive-value")
    monkeypatch.setenv("DATABASE_URL_FILE", str(tmp_path / "absent"))
    with pytest.raises(ConfigurationError) as error:
        Settings.load()
    assert "sensitive-value" not in str(error.value)


def test_no_sqlite_fallback_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ConfigurationError, match="postgresql"):
        Settings.load()


def test_password_utf8_byte_limit():
    with pytest.raises(ValueError):
        security.hash_password("á" * 37)
    assert not security.verify_password("a" * 73, security.hash_password("valid-password"))
    with pytest.raises(ValidationError):
        TouristCreate(
            name="A", surname="B", email="a@example.com", password="á" * 37,
            phone="12345", country_of_origin="BR", cpf="123",
        )


@pytest.fixture
def account(db_session):
    user = User(role=UserRole.tourist, name="A", surname="B", email="s1@example.com",
                password_hash=security.hash_password("valid-password"), country_of_origin="Brasil")
    db_session.add(user)
    db_session.commit()
    return user


def start(db_session):
    return login(LoginRequest(email="s1@example.com", password="valid-password"), db_session)


def test_refresh_rotation_replay_revokes_descendants(db_session, account):
    initial = start(db_session)
    renewed = refresh(RefreshRequest(refresh_token=initial.refresh_token), db_session)
    assert renewed.refresh_token != initial.refresh_token
    with pytest.raises(ApiError):
        refresh(RefreshRequest(refresh_token=initial.refresh_token), db_session)
    with pytest.raises(ApiError):
        refresh(RefreshRequest(refresh_token=renewed.refresh_token), db_session)


def test_logout_revokes_family_and_is_idempotent(db_session, account):
    initial = start(db_session)
    payload = RefreshRequest(refresh_token=initial.refresh_token)
    logout(payload, db_session)
    logout(payload, db_session)
    with pytest.raises(ApiError):
        refresh(payload, db_session)


def test_disabled_user_cannot_refresh(db_session, account):
    initial = start(db_session)
    account.is_active = False
    db_session.commit()
    with pytest.raises(ApiError):
        refresh(RefreshRequest(refresh_token=initial.refresh_token), db_session)


def test_untracked_refresh_rejected(db_session, account):
    token = security.create_refresh_token(account.id, "tourist")
    with pytest.raises(ApiError):
        refresh(RefreshRequest(refresh_token=token), db_session)


def test_admin_bootstrap_preserves_password_and_rejects_other_role(db_session, account):
    spec = importlib.util.spec_from_file_location("bootstrap", Path("scripts/create_admin.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.create_admin(db_session, "admin@example.com", "first-password")
    assert not module.create_admin(db_session, "admin@example.com", "other-password")
    admin = db_session.query(User).filter_by(email="admin@example.com").one()
    assert security.verify_password("first-password", admin.password_hash)
    with pytest.raises(ConfigurationError):
        module.create_admin(db_session, account.email, "other-password")


def test_hmac_and_encryption_keys_cannot_be_shared(monkeypatch):
    monkeypatch.setenv("PII_HMAC_KEY", security.secret("PII_ENCRYPTION_KEY"))
    with pytest.raises(ConfigurationError, match="independent"):
        validate_service("auth")
