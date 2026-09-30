"""Apoio aos testes: acesso ao PostgreSQL local e configuração da API para testes.

Fica fora do `conftest.py` para que os testes importem daqui, e não do `conftest`,
que o pytest carrega por conta própria.
"""

from pathlib import Path
from urllib.parse import quote

import asyncpg
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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


async def garantir_banco_de_teste(config: ConfiguracaoTeste) -> None:
    conexao = await asyncpg.connect(config.url("postgres", driver="postgresql"))
    try:
        existe = await conexao.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", config.postgres_db_teste
        )
        if not existe:
            await conexao.execute(f'CREATE DATABASE "{config.postgres_db_teste}"')
    finally:
        await conexao.close()


def configuracao_para(database_url: str, **parametros: object) -> Configuracao:
    return Configuracao(
        database_url=SecretStr(database_url),
        segredo_sessao=SecretStr("segredo-apenas-para-testes"),
        **parametros,
    )
