"""Maintenance-only PII re-encryption and optional HMAC reindexing.

Stop auth writes and back up database + old keys before invoking. Set the
encryption key ring to new,old; PII_HMAC_KEY is the target uniqueness key.
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from services.auth.app.models.user import User
from shared.db import create_service_engine, make_session_factory
from shared.security import decrypt_pii, encrypt_pii, pii_uniqueness_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rehash", action="store_true", help="Rebuild CPF/passport uniqueness with target HMAC key")
    args = parser.parse_args()
    engine = create_service_engine()
    try:
        with make_session_factory(engine)() as db, db.begin():
            users = db.scalars(select(User).with_for_update()).all()
            documents: set[str] = set()
            count = 0
            for user in users:
                for field in ("phone", "cpf", "passport"):
                    encrypted = getattr(user, f"{field}_encrypted")
                    if encrypted is None:
                        continue
                    plain = decrypt_pii(encrypted)
                    setattr(user, f"{field}_encrypted", encrypt_pii(plain))
                    if args.rehash and field != "phone":
                        digest = pii_uniqueness_hash(plain)
                        if digest in documents:
                            raise ValueError("Duplicate document detected; transaction rolled back")
                        documents.add(digest)
                        setattr(user, f"{field}_hash", digest)
                count += 1
        print(f"PII rotation committed for {count} accounts; no plaintext emitted.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
