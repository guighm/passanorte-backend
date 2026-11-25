"""Copy frozen S1 databases into an already migrated S2 rehearsal database."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

# Parent tables first. The target's foreign keys and unique constraints stay enabled.
TABLES = {
    "auth": ("users", "tourist_profiles", "tourist_interests", "refresh_sessions", "audit_logs"),
    "catalog": ("categories", "tourist_spots", "spot_categories", "opening_schedules", "events", "audit_logs"),
    "gamification": ("prizes", "routes", "route_points", "route_enrollments", "badges", "redeem_codes", "audit_logs"),
    "validation": ("visits",),
    "insights": ("access_logs", "visit_facts"),
    "notifications": ("notification_subscriptions", "notifications"),
    "chatbot": ("conversations", "messages", "embedded_contents"),
}

LINKS = (
    ("gamification.visits", "user_id", "auth.users"),
    ("gamification.visits", "tourist_spot_id", "catalog.tourist_spots"),
    ("catalog.route_points", "tourist_spot_id", "catalog.tourist_spots"),
    ("catalog.routes", "prize_id", "gamification.prizes"),
    ("gamification.route_enrollments", "route_id", "catalog.routes"),
    ("gamification.badges", "route_id", "catalog.routes"),
    ("gamification.redeem_codes", "route_id", "catalog.routes"),
    ("gamification.route_enrollments", "user_id", "auth.users"),
    ("auth.tourist_interests", "category_id", "catalog.categories"),
)


def export(connection: psycopg.Connection, schema: str, name: str, columns: list[str]) -> Iterator[memoryview]:
    identifiers = sql.SQL(", ").join(map(sql.Identifier, columns))
    query = sql.SQL("COPY (SELECT {} FROM {} ORDER BY {}) TO STDOUT").format(
        identifiers, sql.Identifier(schema, name), identifiers,
    )
    with connection.cursor().copy(query) as copy:
        yield from copy


def fingerprint(connection: psycopg.Connection, schema: str, name: str, columns: list[str]) -> str:
    digest = hashlib.sha256()
    for chunk in export(connection, schema, name, columns):
        digest.update(chunk)
    return digest.hexdigest()


def copy_table(
    source: psycopg.Connection, target: psycopg.Connection, schema: str, name: str,
) -> dict[str, Any]:
    source_name = sql.Identifier("public", name)
    target_name = sql.Identifier(schema, name)
    cursor = source.execute(sql.SQL("SELECT * FROM {} LIMIT 0").format(source_name))
    columns = [column.name for column in cursor.description or ()]
    source_count = source.execute(sql.SQL("SELECT count(*) FROM {}").format(source_name)).fetchone()[0]
    target_count = target.execute(sql.SQL("SELECT count(*) FROM {}").format(target_name)).fetchone()[0]
    if source_count and not target_count:
        query = sql.SQL("COPY {} ({}) FROM STDIN").format(
            target_name, sql.SQL(", ").join(map(sql.Identifier, columns)),
        )
        with target.cursor().copy(query) as copy:
            for chunk in export(source, "public", name, columns):
                copy.write(chunk)
        target_count = target.execute(sql.SQL("SELECT count(*) FROM {}").format(target_name)).fetchone()[0]
    same = target_count == source_count and (
        fingerprint(source, "public", name, columns) == fingerprint(target, schema, name, columns)
    )
    if not same:
        raise ValueError(f"Divergence in {schema}.{name}; transaction rolled back")
    return {"table": f"{schema}.{name}", "source_rows": source_count, "target_rows": target_count, "exact_match": same}


def unmatched_links(target: psycopg.Connection) -> list[dict]:
    results = []
    for source, column, destination in LINKS:
        query = sql.SQL(
            "SELECT count(*) FROM {} a LEFT JOIN {} b ON a.{} = b.id WHERE a.{} IS NOT NULL AND b.id IS NULL"
        ).format(
            sql.Identifier(*source.split(".")), sql.Identifier(*destination.split(".")),
            sql.Identifier(column), sql.Identifier(column),
        )
        missing = target.execute(query).fetchone()[0]
        results.append({"source": source, "column": column, "target": destination, "unmatched": missing})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Files named auth.dsn, catalog.dsn, etc.")
    parser.add_argument("--target-dsn-file", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--commit", action="store_true",
                        help="Retain the import in the isolated rehearsal target. Default rolls it back.")
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Choose a new report path")
    report: dict[str, Any] = {"started_at": datetime.now(UTC).isoformat(), "tables": []}
    current = "target connection"
    try:
        with ExitStack() as stack:
            target = stack.enter_context(psycopg.connect(args.target_dsn_file.read_text().strip()))
            if target.info.dbname != "passanorte":
                raise ValueError("Target database must be named passanorte")
            target.execute("SELECT pg_advisory_xact_lock(7202302)")
            target.execute("SET LOCAL TIME ZONE 'UTC'")
            for domain, tables in TABLES.items():
                current = f"source {domain}"
                source = stack.enter_context(psycopg.connect((args.source_dir / f"{domain}.dsn").read_text().strip()))
                source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                source.execute("SET LOCAL TIME ZONE 'UTC'")
                schema = "gamification" if domain == "validation" else domain
                for name in tables:
                    current = f"{domain}.{name}"
                    target_schema = schema
                    if domain == "gamification" and name in {"routes", "route_points"}:
                        target_schema = "catalog"
                    report["tables"].append(copy_table(source, target, target_schema, name))
            report["cross_domain_links"] = unmatched_links(target)
            count = target.execute("SELECT count(*) FROM auth.users WHERE role::text = 'employee'").fetchone()[0]
            report["legacy_employee_accounts"] = count
            if any(link["unmatched"] for link in report["cross_domain_links"]):
                current = "cross-domain links"
                raise ValueError("Cross-domain links need reconciliation")
            report["committed"] = args.commit
            if not args.commit:
                target.rollback()
    except Exception as error:
        report.update(committed=False, failed_at=current, error_type=type(error).__name__)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise SystemExit(f"Reconciliation failed at {current}; see the report.") from None
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
