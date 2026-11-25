"""Create synthetic S1 data and verify migration in an isolated Compose project."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg
from migrate_legacy import TABLES
from psycopg import sql
from psycopg.conninfo import make_conninfo
from sqlalchemy.engine import URL

LEGACY_DIR = Path(__file__).resolve().parent


def main() -> None:
    password = Path(os.environ["POSTGRES_PASSWORD_FILE"]).read_text().strip()
    connection_args = {"host": "db", "user": "passanorte", "password": password}
    target_dsn = make_conninfo(dbname="passanorte", **connection_args)
    with TemporaryDirectory() as directory:
        files = Path(directory)
        for service in TABLES:
            database = f"passanorte_{service}"
            with psycopg.connect(target_dsn, autocommit=True) as connection:
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            source_dsn = make_conninfo(dbname=database, **connection_args)
            (files / f"{service}.dsn").write_text(source_dsn)
            if service == "chatbot":
                with psycopg.connect(source_dsn) as chatbot:
                    chatbot.execute("CREATE EXTENSION IF NOT EXISTS vector")
            url = URL.create("postgresql+psycopg", database=database, username="passanorte", host="db",
                             password=password)
            subprocess.run(
                ["alembic", "-c", f"src/services/{service}/alembic.ini", "upgrade", "head"],
                cwd=LEGACY_DIR, check=True,
                env={**os.environ, "APP_ENV": "test", "PYTHONPATH": str(LEGACY_DIR / "src"),
                     "DATABASE_URL": url.render_as_string(hide_password=False)},
            )
        (files / "target.dsn").write_text(target_dsn)
        with psycopg.connect((files / "auth.dsn").read_text()) as auth:
            auth.execute(
                "INSERT INTO users (id, role, name, surname, email, password_hash, country_of_origin, is_active) "
                "VALUES ('employee-s2', 'employee', 'Pessoa', 'Fictícia', 'legacy@example.com', "
                "'fixture', 'Brasil', true)"
            )
            auth.execute(
                "INSERT INTO refresh_sessions (jti_hash, family_id, user_id, expires_at, revoked) "
                "VALUES ('legacy-session-s2', 'legacy-family-s2', 'employee-s2', 4102444800, false)"
            )
        with psycopg.connect((files / "catalog.dsn").read_text()) as catalog:
            catalog.execute(
                "INSERT INTO tourist_spots "
                "(id, name, description, latitude, longitude, status, tolerance_radius_m, is_removed) "
                "VALUES ('spot-s2', 'Ponto fictício', 'Ensaio S2', -3.1, -60, 'open', 50, false)"
            )
        with psycopg.connect((files / "gamification.dsn").read_text()) as gamification:
            gamification.execute(
                "INSERT INTO prizes (id, name, stock_quantity) VALUES ('prize-s2', 'Prêmio fictício', 1)"
            )
            gamification.execute(
                "INSERT INTO routes (id, name, prize_id, is_active) "
                "VALUES ('route-s2', 'Rota fictícia', 'prize-s2', true)"
            )
            gamification.execute(
                "INSERT INTO route_points (id, route_id, tourist_spot_id, position, is_active) "
                "VALUES ('point-s2', 'route-s2', 'spot-s2', 1, true)"
            )
            gamification.execute(
                "INSERT INTO audit_logs (id, actor_id, action, entity, entity_id, occurred_at) "
                "VALUES ('audit-s2', 'employee-s2', 'redeem', 'prize', 'prize-s2', '2026-01-02T03:04:05')"
            )
        command = [
            sys.executable, "/app/scripts/migrate_legacy.py",
            "--source-dir", str(files), "--target-dsn-file", str(files / "target.dsn"),
        ]
        with psycopg.connect(target_dsn, autocommit=True) as target:
            for stage, commit in (("dry-run", False), ("commit", True), ("retry", True)):
                report_file = files / f"{stage}.json"
                subprocess.run(
                    [*command, "--report", str(report_file), *(["--commit"] if commit else [])],
                    check=True,
                )
                report = json.loads(report_file.read_text(encoding="utf-8"))
                assert report["committed"] == commit
                assert len(report["tables"]) == sum(map(len, TABLES.values()))
                assert all(table["exact_match"] for table in report["tables"])
                assert all(link["unmatched"] == 0 for link in report["cross_domain_links"])
                assert report["legacy_employee_accounts"] == 1
                point = target.execute(
                    "SELECT p.id, r.id, s.id, r.prize_id FROM catalog.route_points p "
                    "JOIN catalog.routes r ON r.id = p.route_id "
                    "JOIN catalog.tourist_spots s ON s.id = p.tourist_spot_id WHERE p.id = 'point-s2'"
                ).fetchone()
                assert point == (("point-s2", "route-s2", "spot-s2", "prize-s2") if commit else None)
                print(json.dumps({"stage": stage, **report}, ensure_ascii=True), flush=True)
    print("S2 synthetic legacy migration checks passed.")


if __name__ == "__main__":
    main()
