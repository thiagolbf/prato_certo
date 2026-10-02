"""Configuração da aplicação, lida de variáveis de ambiente (ADR-008, RN-47).

Fora do container, também lê o `.env` da raiz do repositório, para a API rodar direto
no terminal. Variável de ambiente tem prioridade sobre o arquivo; no container o `.env`
não existe e tudo vem do ambiente montado pelo Docker Compose ou pela plataforma.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# api/app/core/config.py → raiz do repositório.
ARQUIVO_ENV = Path(__file__).resolve().parents[3] / ".env"


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=ARQUIVO_ENV, extra="ignore")
    # Segredos: obrigatórios e sem valor padrão, para nunca existirem no código (RN-47).
    database_url: SecretStr
    segredo_sessao: SecretStr

    port: int = 8000
    # Tempo máximo para conectar e para o /health: sem ele, o asyncpg espera até 60 s.
    banco_timeout_segundos: float = 5.0

    # Parâmetros definidos na seção 3 do PLAN-001, ajustáveis sem mudar código.
    sessao_inatividade_admin_min: int = 30
    sessao_inatividade_operador_min: int = 12 * 60
    bloqueio_tentativas: int = 5
    bloqueio_minutos: list[int] = Field(default_factory=lambda: [1, 5, 15, 60])
    corpo_maximo_bytes: int = 16 * 1024
    forcar_https: bool = False


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
