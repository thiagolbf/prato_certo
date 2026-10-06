"""Apoio aos testes: acesso ao PostgreSQL local e configuração da API para testes.

Fica fora do `conftest.py` para que os testes importem daqui, e não do `conftest`,
que o pytest carrega por conta própria.
"""

from pathlib import Path
from urllib.parse import quote

import asyncpg
from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import Connection

from app.core.config import Configuracao

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[2]


class ConfiguracaoTeste(BaseSettings):
    """Credenciais do PostgreSQL local, lidas do ambiente ou do `.env` da raiz do repositório."""

    model_config = SettingsConfigDict(env_file=RAIZ_DO_REPOSITORIO / ".env", extra="ignore")

    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str = "localhost"
    postgres_porta: int = 5432
    postgres_db_teste: str = "pfmarmitas_test"

    def url(self, banco: str, driver: str = "postgresql+asyncpg") -> str:
        usuario = quote(self.postgres_user, safe="")
        senha = quote(self.postgres_password.get_secret_value(), safe="")
        return f"{driver}://{usuario}:{senha}@{self.postgres_host}:{self.postgres_porta}/{banco}"


async def recriar_banco_de_teste(config: ConfiguracaoTeste) -> None:
    """Banco de teste vazio a cada execução: o esquema é sempre o das migrations em disco,
    mesmo quando uma migration já aplicada foi editada depois."""
    await remover_banco(config, config.postgres_db_teste)
    await criar_banco(config, config.postgres_db_teste)


async def criar_banco(config: ConfiguracaoTeste, banco: str) -> None:
    conexao = await asyncpg.connect(config.url("postgres", driver="postgresql"))
    try:
        existe = await conexao.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", banco)
        if not existe:
            await conexao.execute(f'CREATE DATABASE "{banco}"')
    finally:
        await conexao.close()


async def remover_banco(config: ConfiguracaoTeste, banco: str) -> None:
    conexao = await asyncpg.connect(config.url("postgres", driver="postgresql"))
    try:
        await conexao.execute(f'DROP DATABASE IF EXISTS "{banco}" WITH (FORCE)')
    finally:
        await conexao.close()


def aplicar_migrations(conexao: Connection, revisao: str = "head") -> None:
    """Roda `alembic upgrade` na conexão dada; usar com `AsyncConnection.run_sync`."""
    command.upgrade(_config_alembic(conexao), revisao)


def desfazer_migrations(conexao: Connection, revisao: str = "base") -> None:
    """Roda `alembic downgrade` na conexão dada; usar com `AsyncConnection.run_sync`."""
    command.downgrade(_config_alembic(conexao), revisao)


def revisao_mais_recente() -> str | None:
    """Última revisão das migrations em disco (o `head` do Alembic)."""
    return ScriptDirectory.from_config(_config_alembic()).get_current_head()


def _config_alembic(conexao: Connection | None = None) -> AlembicConfig:
    config = AlembicConfig(str(RAIZ_DO_REPOSITORIO / "api" / "alembic.ini"))
    if conexao is not None:
        config.attributes["connection"] = conexao
    return config


def configuracao_para(database_url: str, **parametros: object) -> Configuracao:
    return Configuracao(
        database_url=SecretStr(database_url),
        segredo_sessao=SecretStr("segredo-apenas-para-testes"),
        **parametros,
    )
