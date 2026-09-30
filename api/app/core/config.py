"""Configuração da aplicação, lida só de variáveis de ambiente (ADR-008, RN-47)."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Configuracao(BaseSettings):
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
