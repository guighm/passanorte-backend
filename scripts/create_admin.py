"""Geração de credencial inicial do admin (RF01) — T025.

Uso:
    uv run python scripts/create_admin.py --email admin@passanorte.com --password '...'
    uv run python scripts/create_admin.py            # gera senha aleatória e imprime
    uv run python scripts/create_admin.py --email ... --if-missing  # só cria se o email for novo
"""

from __future__ import annotations

import argparse
import secrets
import sys

sys.path.insert(0, "src")

from services.auth.app.models.user import User, UserRole  # noqa: E402
from shared.db import create_service_engine, database_url, make_session_factory  # noqa: E402
from shared.security import hash_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria a credencial inicial do admin (RF01).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="se omitido, uma senha forte é gerada e impressa")
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--surname", default="PassaNorte")
    parser.add_argument("--if-missing", action="store_true",
                        help="não falha nem cria nada se o email já existir "
                             "(usado pelo seed one-shot do compose)")
    args = parser.parse_args()

    password = args.password or (secrets.token_urlsafe(16) + "Aa1!")
    database_url()  # valida DATABASE_URL cedo
    engine = create_service_engine()
    factory = make_session_factory(engine)
    db = factory()
    try:
        existing = db.query(User).filter(User.email == args.email).first()
        if existing is not None:
            if args.if_missing:
                print(f"admin já existe: {args.email} — nada a fazer.")
                return 0
            print(f"erro: email {args.email} já cadastrado.", file=sys.stderr)
            return 1
        user = User(
            role=UserRole.admin,
            name=args.name,
            surname=args.surname,
            email=args.email,
            password_hash=hash_password(password),
            country_of_origin="Brasil",
        )
        db.add(user)
        db.commit()
        print(f"admin criado: {args.email}")
        if not args.password:
            print(f"senha gerada: {password}")
        return 0
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
