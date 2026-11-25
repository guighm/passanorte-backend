# Identical pinned Python base in builder/runtime; update digests deliberately.
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv
FROM python:3.11.17-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11.17-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf AS runtime
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src /app/src
COPY --chown=app:app scripts/apply_migrations.sh scripts/create_admin.py scripts/rotate_pii.py scripts/provision_database.py scripts/migrate_legacy.py /app/scripts/
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
CMD ["uvicorn", "services.auth.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
