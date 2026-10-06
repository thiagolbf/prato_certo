"""Migrations do Alembic: o banco nasce delas, nunca de `create_all` (ADR-003, T-03)."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from tests.apoio import (
    ConfiguracaoTeste,
    aplicar_migrations,
    criar_banco,
    desfazer_migrations,
    remover_banco,
    revisao_mais_recente,
)

BANCO_VAZIO = "pfmarmitas_test_migrations"


@pytest.fixture
async def engine_banco_vazio(config_teste: ConfiguracaoTeste) -> AsyncIterator[AsyncEngine]:
    """Banco recém-criado, sem nenhuma tabela, só para este teste."""
    await remover_banco(config_teste, BANCO_VAZIO)
    await criar_banco(config_teste, BANCO_VAZIO)
    engine = create_async_engine(config_teste.url(BANCO_VAZIO))
    try:
        yield engine
    finally:
        await engine.dispose()
        await remover_banco(config_teste, BANCO_VAZIO)


async def _tabela_existe(engine: AsyncEngine, tabela: str) -> bool:
    async with engine.connect() as conexao:
        return await conexao.scalar(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": tabela})


async def test_migration_inicial_semeia_um_unico_estabelecimento(
    engine_banco_vazio: AsyncEngine,
) -> None:
    async with engine_banco_vazio.begin() as conexao:
        await conexao.run_sync(aplicar_migrations)

    async with engine_banco_vazio.connect() as conexao:
        nomes = (await conexao.scalars(text("SELECT nome FROM estabelecimento"))).all()
    assert nomes == ["Meu restaurante"]


async def test_downgrade_base_desfaz_a_migration_inicial(engine_banco_vazio: AsyncEngine) -> None:
    async with engine_banco_vazio.begin() as conexao:
        await conexao.run_sync(aplicar_migrations)
    async with engine_banco_vazio.begin() as conexao:
        await conexao.run_sync(desfazer_migrations)

    assert not await _tabela_existe(engine_banco_vazio, "estabelecimento")


async def test_banco_de_teste_vem_das_migrations(sessao: AsyncSession) -> None:
    """O conftest aplica as migrations: a tabela de versão do Alembic está na última revisão."""
    versao = await sessao.scalar(text("SELECT version_num FROM alembic_version"))

    assert versao == revisao_mais_recente()
