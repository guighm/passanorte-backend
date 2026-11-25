"""Idempotent admin bootstrap. Password from ADMIN_PASSWORD_FILE or hidden prompt."""
from __future__ import annotations

import argparse
import getpass
import sys

from services.auth.app.models.user import User, UserRole
from shared.db import create_service_engine, make_session_factory
from shared.security import hash_password
from shared.settings import ConfigurationError, secret


def create_admin(db, email: str, password: str, name: str = "Admin", surname: str = "PassaNorte") -> bool:
    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        if existing.role != UserRole.admin or not existing.is_active:
            raise ConfigurationError("Bootstrap email belongs to a non-admin or inactive account")
        return False
    db.add(User(
        role=UserRole.admin, name=name, surname=surname, email=email,
        password_hash=hash_password(password), country_of_origin="Brasil",
    ))
    db.commit()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--if-missing", action="store_true", help="Compatibility flag; always idempotent")
    args = parser.parse_args()
    engine = create_service_engine()
    try:
        with make_session_factory(engine)() as db:
            existing = db.query(User).filter(User.email == args.email).first()
            password = ""
            if existing is None:
                password = secret("ADMIN_PASSWORD", required=False)
                if not password and sys.stdin.isatty():
                    password = getpass.getpass("Admin password: ")
                if not password:
                    raise ConfigurationError("Supply ADMIN_PASSWORD_FILE or use an interactive terminal")
            created = create_admin(db, args.email, password)
            print("Admin created." if created else "Admin already exists; unchanged.")
        return 0
    except (ConfigurationError, ValueError):
        print("Admin bootstrap failed: check configuration, password policy and account role.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
