# PassaNorte — imagem base dos 7 microsserviços (RNF15: custo zero, imagem leve)
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# dependências primeiro (cache de camadas)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

EXPOSE 8001
# comando por serviço é definido no docker-compose (uvicorn services.<svc>.app.main:app,
# resolvido via /app/src no PYTHONPATH)
CMD ["python", "-c", "print('use docker-compose para escolher o serviço na porta certa')"]