"""Ambiente do Alembic em modo async (T-03).

Pela linha de comando, conecta na `DATABASE_URL` da configuração da API (ADR-008).
Chamado pelo código, como nos testes, usa a conexão recebida em
`config.attributes["connection"]` e não mexe na configuração de log de quem chamou.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.catalogo.modelos  # noqa: F401

# Registro dos modelos na metadata: todo módulo com modelo SQLAlchemy entra aqui.
# Modelo não importado fica invisível ao --autogenerate, que gera migration vazia sem
# avisar; `uv run alembic check` acusa modelo e migrations fora de sincronia.
import app.core.estabelecimento  # noqa: F401
import app.identidade.modelos  # noqa: F401
from app.core.config import obter_configuracao
from app.core.modelo_base import Base

config = context.config
conexao_recebida: Connection | None = config.attributes.get("connection")

if config.config_file_name is not None and conexao_recebida is None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url_do_banco() -> str:
    return obter_configuracao().database_url.get_secret_value()


def run_migrations_offline() -> None:
    """Gera o SQL das migrations sem conectar (`alembic upgrade head --sql`)."""
    context.configure(
        url=_url_do_banco(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_url_do_banco(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif conexao_recebida is not None:
    do_run_migrations(conexao_recebida)
else:
    asyncio.run(run_async_migrations())
