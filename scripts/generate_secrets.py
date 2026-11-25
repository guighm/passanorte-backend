"""Generate local development secrets without replacing persistent credentials."""
from __future__ import annotations

import argparse
import ipaddress
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SERVICES = ("auth", "catalog", "gamification", "benefits", "insights", "notifications", "chatbot")


def private_pem(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    )


def s1_secrets() -> dict[str, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    rabbit_password = secrets.token_urlsafe(32)
    return {
        "jwt-private.key": private_pem(key),
        "public/key-1.pem": key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        "pii.key": Fernet.generate_key(),
        "pii-hmac.key": secrets.token_urlsafe(48).encode(),
        "admin-password": secrets.token_urlsafe(32).encode(),
        "postgres-password": secrets.token_urlsafe(32).encode(),
        "rabbit-password": rabbit_password.encode(),
        "rabbit-url": f"amqp://passanorte:{rabbit_password}@rabbitmq:5672/".encode(),
    }


def s2_secrets() -> dict[str, bytes]:
    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(tls_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]), critical=False)
        .sign(tls_key, hashes.SHA256())
    )
    result = {
        "internal-api-token": secrets.token_urlsafe(48).encode(),
        "edge.crt": certificate.public_bytes(serialization.Encoding.PEM),
        "edge.key": private_pem(tls_key),
    }
    for domain in SERVICES:
        for kind in ("migrator", "runtime"):
            role = f"{domain}_{kind}"
            password = secrets.token_urlsafe(32)
            result[f"database-{role}"] = f"postgresql+psycopg://{role}:{password}@db:5432/passanorte".encode()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("secrets"))
    parser.add_argument("--add-s2", action="store_true", help="Extend an existing S1 secret directory")
    args = parser.parse_args()
    root = args.directory
    if args.add_s2:
        if not root.is_dir():
            parser.error("--add-s2 requires the existing S1 secrets directory")
        files = s2_secrets()
    else:
        if root.exists():
            parser.error("Destination already exists")
        root.mkdir(mode=0o700, parents=True)
        (root / "public").mkdir(mode=0o755)
        files = {**s1_secrets(), **s2_secrets()}
    if any((root / name).exists() for name in files):
        parser.error("An output secret already exists")
    for name, value in files.items():
        path = root / name
        with path.open("xb") as output:
            output.write(value)
        # Compose's file-backed secrets are mounted read-only in non-root containers.
        os.chmod(path, 0o444)
    print("Development secret files created. Protect the enclosing directory with host ACLs.")


if __name__ == "__main__":
    main()
