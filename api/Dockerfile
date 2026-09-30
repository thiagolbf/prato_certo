# Mesmo Dockerfile no Docker Compose local e no Render (ADR-008).
# Versão fixa, para o build local e o do Render gerarem a mesma imagem;
# atualizar de propósito, conferindo o patch de segurança do Python e do Debian.
FROM python:3.12.14-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

# Dependências primeiro, para o cache de camada sobreviver a mudança só de código.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

# Escuta na porta informada pela plataforma em $PORT (ADR-008).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\""]
