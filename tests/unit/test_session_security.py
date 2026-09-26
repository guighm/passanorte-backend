"""T012 [US1] Testes unitários de sessão/senha/PII (Princípio IV).

Valida os helpers de shared/security.py usados pela autenticação do turista:
JWT access/refresh, bcrypt e criptografia de PII com unicidade HMAC.
"""

import jwt
import pytest

from shared import security

# --- JWT --------------------------------------------------------------------

def test_access_token_carries_sub_role_and_expiry():
    token, expires_in = security.create_access_token("user-1", "tourist")
    claims = security.decode_token(token, expected_type="access")
    assert claims["sub"] == "user-1"
    assert claims["role"] == "tourist"
    assert expires_in == security.ACCESS_TOKEN_MINUTES * 60


def test_access_token_expires():
    token, _ = security.create_access_token("user-1", "tourist")
    claims = security.decode_token(token)
    assert claims["exp"] > claims["iat"]


def test_refresh_token_is_rejected_as_access():
    refresh = security.create_refresh_token("user-1", "tourist")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(refresh, expected_type="access")


def test_tampered_token_is_rejected():
    token, _ = security.create_access_token("user-1", "tourist")
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(token + "tampered")


# --- Senhas -----------------------------------------------------------------

def test_password_hash_is_bcrypt_and_not_plaintext():
    hashed = security.hash_password("s3cr3t!x")
    assert hashed != "s3cr3t!x"
    assert hashed.startswith("$2b$")


def test_password_verify_roundtrip():
    hashed = security.hash_password("s3cr3t!x")
    assert security.verify_password("s3cr3t!x", hashed)
    assert not security.verify_password("wrong", hashed)


# --- PII --------------------------------------------------------------------

def test_pii_encrypt_decrypt_roundtrip():
    encrypted = security.encrypt_pii("123.456.789-00")
    assert "123.456.789-00" not in encrypted
    assert security.decrypt_pii(encrypted) == "123.456.789-00"


def test_pii_uniqueness_hash_is_deterministic_and_case_insensitive():
    assert security.pii_uniqueness_hash("ABC") == security.pii_uniqueness_hash("abc")
    assert security.pii_uniqueness_hash("ABC") != security.pii_uniqueness_hash("ABD")
