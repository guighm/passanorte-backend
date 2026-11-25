#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Run on a development stack with the default S2 smoke settings.
compose=(docker compose --env-file .env.example "$@")
# Always restore the broker if a check fails during the simulated outage.
trap '"${compose[@]}" start rabbitmq' EXIT
"${compose[@]}" stop rabbitmq
"${compose[@]}" exec -T auth python - <<'PY'
from time import sleep
from urllib.error import HTTPError
from urllib.request import urlopen

for _ in range(20):
    try:
        with urlopen("http://127.0.0.1:8001/ready", timeout=2):
            pass
    except HTTPError as error:
        assert error.code == 503
        break
    sleep(1)
else:
    raise AssertionError("Auth stayed ready while RabbitMQ was stopped")
PY
request_id=$(uv run --frozen python - <<'PY'
import ssl
from pathlib import Path
from uuid import uuid4

import httpx

context = ssl.create_default_context(cafile="secrets/edge.crt")
request_id = uuid4().hex
httpx.post(
    "https://localhost:8443/api/v1/session",
    verify=context,
    headers={"X-Request-Id": request_id},
    json={"email": "admin@example.com", "password": Path("secrets/admin-password").read_text().strip()},
).raise_for_status()
print(request_id)
PY
)
[[ "$request_id" =~ ^[0-9a-f]{32}$ ]]
query() {
  "${compose[@]}" exec -T db psql -XAt -v ON_ERROR_STOP=1 -U passanorte -d passanorte -c "$1"
}
event_id=$(query "SELECT event_id FROM auth.outbox WHERE envelope->>'event_type' = 'access.registered' AND envelope->>'correlation_id' = '$request_id'")
[[ "$event_id" =~ ^[0-9a-f]{32}$ ]]
auth_container=$("${compose[@]}" ps -q auth)
previous_restarts=$(docker inspect --format '{{.RestartCount}}' "$auth_container")
"${compose[@]}" exec -T auth python - <<'PY'
import os
import signal
from pathlib import Path

for pid in Path("/proc/1/task/1/children").read_text().split():
    if b"services.auth.app.main:app" in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0"):
        os.kill(int(pid), signal.SIGTERM)
        break
else:
    raise AssertionError("Auth process was not found")
PY
for attempt in {1..30}; do
  restarts=$(docker inspect --format '{{.RestartCount}}' "$auth_container")
  if (( restarts > previous_restarts )); then
    break
  fi
  sleep 1
done
(( restarts > previous_restarts ))
"${compose[@]}" start rabbitmq
trap - EXIT
"${compose[@]}" up -d --wait --wait-timeout 180
for attempt in {1..30}; do
  processed=$(query "SELECT count(*) FROM insights.inbox WHERE event_id = '$event_id'")
  if [[ "$processed" == 1 ]]; then
    break
  fi
  sleep 1
done
[[ "$processed" == 1 ]]
uv run --frozen python scripts/smoke_s2.py --email admin@example.com
echo "S2 readiness, automatic restart and event recovery checks passed."
