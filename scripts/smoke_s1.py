"""Read-only health/schema checks plus an isolated admin session lifecycle."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password-file", type=Path, default=Path("secrets/admin-password"))
    args = parser.parse_args()
    with httpx.Client(timeout=15, trust_env=False) as client:
        for port in range(8001, 8008):
            base = f"http://127.0.0.1:{port}"
            assert client.get(base + "/health").status_code == 200, f"Health failed: {port}"
            schema = client.get(base + "/openapi.json")
            assert schema.status_code == 200 and schema.json()["paths"], f"OpenAPI failed: {port}"
            assert client.get(base + "/docs").status_code == 200, f"Swagger failed: {port}"
        base = "http://127.0.0.1:8000/api/v1"
        assert client.get(base + "/me").status_code == 401
        response = client.post(base + "/session", json={
            "email": args.email, "password": args.password_file.read_text().strip(),
        })
        assert response.status_code == 200, "Login failed"
        tokens = response.json()
        headers = {"Authorization": "Bearer " + tokens["access_token"]}
        assert client.get(base + "/me", headers=headers).status_code == 200
        assert client.get(base + "/me", headers={
            "Authorization": "Bearer " + tokens["refresh_token"],
        }).status_code == 401
        renewed = client.post(base + "/session/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert renewed.status_code == 200
        payload = {"refresh_token": renewed.json()["refresh_token"]}
        assert client.request("DELETE", base + "/session", headers=headers, json=payload).status_code == 204
        assert client.post(base + "/session/refresh", json=payload).status_code == 401
        # Concurrent PostgreSQL refresh: exactly one rotation succeeds; replay revokes descendants.
        tokens = client.post(base + "/session", json={
            "email": args.email, "password": args.password_file.read_text().strip(),
        }).json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda _: client.post(base + "/session/refresh", json={"refresh_token": tokens["refresh_token"]}),
                range(2),
            ))
        assert sorted(r.status_code for r in results) == [200, 401], "Concurrent refresh not single-use"
        winner = next(r for r in results if r.status_code == 200)
        assert client.post(base + "/session/refresh", json={
            "refresh_token": winner.json()["refresh_token"],
        }).status_code == 401
    print("S1 smoke passed: 7 services, Swagger, Kong RS256, refresh/logout and PostgreSQL concurrency.")


if __name__ == "__main__":
    main()
