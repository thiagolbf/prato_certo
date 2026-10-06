"""Engine async e sessão de banco por requisição (seção 6.2 da proposta, ADR-009)."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Configuracao


def criar_engine(configuracao: Configuracao) -> AsyncEngine:
    return create_async_engine(
        configuracao.database_url.get_secret_value(),
        pool_pre_ping=True,
        # Sem isso, todo erro de consulta traz `[parameters: ...]` na mensagem, e o traceback
        # gravado no log levaria hash de senha e de token (RN-45).
        hide_parameters=True,
        connect_args={"timeout": configuracao.banco_timeout_segundos},
    )


def criar_fabrica_sessoes(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def obter_sessao(request: Request) -> AsyncIterator[AsyncSession]:
    """Dependência do FastAPI: uma `AsyncSession` por requisição."""
    fabrica: async_sessionmaker[AsyncSession] = request.app.state.fabrica_sessoes
    async with fabrica() as sessao:
        yield sessao
