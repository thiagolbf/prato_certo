"""Fixtures comuns: PostgreSQL real do Docker Compose (nunca SQLite) e cliente HTTP da API."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Configuracao
from app.core.db import criar_engine, obter_sessao
from app.main import criar_app
from tests.apoio import ConfiguracaoTeste, configuracao_para, garantir_banco_de_teste


@pytest.fixture(scope="session")
def config_teste() -> ConfiguracaoTeste:
    return ConfiguracaoTeste()


@pytest.fixture(scope="session")
def configuracao(config_teste: ConfiguracaoTeste) -> Configuracao:
    return configuracao_para(config_teste.url(config_teste.postgres_db_teste))


@pytest.fixture(scope="session")
async def engine(
    config_teste: ConfiguracaoTeste, configuracao: Configuracao
) -> AsyncIterator[AsyncEngine]:
    await garantir_banco_de_teste(config_teste)
    engine = criar_engine(configuracao)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessao(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sessão dentro de uma transação desfeita ao final: nenhum teste deixa dado para o próximo."""
    async with engine.connect() as conexao:
        transacao = await conexao.begin()
        sessao = AsyncSession(
            bind=conexao, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield sessao
        finally:
            await sessao.close()
            await transacao.rollback()


@pytest.fixture
async def app(configuracao: Configuracao, sessao: AsyncSession) -> AsyncIterator[FastAPI]:
    app = criar_app(configuracao)
    app.dependency_overrides[obter_sessao] = lambda: sessao
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente:
        yield cliente
