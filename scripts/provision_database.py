"""Provision domain ownership and restricted logins on the dedicated S2 database."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from shared.db import DOMAINS
from shared.settings import secret


def main() -> None:
    directory = Path(os.environ["DB_CREDENTIAL_DIR"])
    with psycopg.connect(
        host="db", user="passanorte", dbname="passanorte",
        password=secret("POSTGRES_PASSWORD"), autocommit=False,
    ) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(7202302)")
        connection.execute("REVOKE ALL ON DATABASE passanorte FROM PUBLIC")
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for domain in DOMAINS:
            owner = sql.Identifier(f"{domain}_owner")
            connection.execute(sql.SQL("DO $$ BEGIN CREATE ROLE {} NOLOGIN; "
                                       "EXCEPTION WHEN duplicate_object THEN NULL; END $$").format(owner))
            connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(
                sql.Identifier(domain), owner,
            ))
            for kind in ("migrator", "runtime"):
                username = f"{domain}_{kind}"
                role = sql.Identifier(username)
                url = make_url((directory / f"database-{username}").read_text().strip())
                if url.username != username or url.database != "passanorte" or not url.password:
                    raise ValueError(f"Invalid database credentials for {username}")
                connection.execute(sql.SQL("DO $$ BEGIN CREATE ROLE {}; "
                                           "EXCEPTION WHEN duplicate_object THEN NULL; END $$").format(role))
                connection.execute(sql.SQL(
                    "ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                    "NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 15 PASSWORD {}"
                ).format(role, sql.Literal(url.password)))
                connection.execute(sql.SQL("GRANT CONNECT ON DATABASE passanorte TO {}").format(role))
                connection.execute(sql.SQL(
                    "ALTER ROLE {} IN DATABASE passanorte SET search_path TO pg_catalog"
                ).format(role))
                connection.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(domain), role))
                if kind == "migrator":
                    connection.execute(sql.SQL("GRANT {} TO {}").format(owner, role))
        # Reserve the extension schema for the existing chatbot adapter.
        connection.execute("CREATE SCHEMA IF NOT EXISTS extensions")
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
        connection.execute("GRANT USAGE ON SCHEMA extensions TO chatbot_runtime, chatbot_owner")


if __name__ == "__main__":
    main()
