"""Alembic bootstrap for a single domain and its dedicated migrator."""
from alembic import context
from sqlalchemy import MetaData, create_engine, pool, text

from shared.db import DOMAINS
from shared.delivery import inbox_table, outbox_table
from shared.settings import secret


def run(domain: str, metadata: MetaData) -> None:
    if domain not in DOMAINS:
        raise ValueError("Unknown migration domain")
    infrastructure = MetaData()
    inbox_table(domain).to_metadata(infrastructure)
    outbox_table(domain).to_metadata(infrastructure)
    engine = create_engine(secret("DATABASE_URL"), poolclass=pool.NullPool, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL ROLE "{domain}_owner"'))
        # Historical revisions use unqualified names. New models are schema-qualified.
        search_path = f'SET LOCAL search_path TO "{domain}", pg_catalog'
        if domain == "chatbot":
            search_path += ", extensions"
        connection.execute(text(search_path))
        context.configure(
            connection=connection,
            target_metadata=[metadata, infrastructure],
            include_schemas=True,
            include_name=lambda name, kind, _: kind != "schema" or name == domain,
            version_table_schema=domain,
        )
        with context.begin_transaction():
            context.run_migrations()
        runtime = f'"{domain}_runtime"'
        connection.execute(text(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{domain}" TO {runtime}'
        ))
        for table in ("alembic_version", "audit_logs", "ledger"):
            if connection.scalar(text("SELECT to_regclass(:name)"), {"name": f"{domain}.{table}"}):
                privileges = "ALL" if table == "alembic_version" else "UPDATE, DELETE, TRUNCATE"
                connection.execute(text(f'REVOKE {privileges} ON "{domain}"."{table}" FROM {runtime}'))
    engine.dispose()
