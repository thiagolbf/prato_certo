"""Engine async e sessão de banco por requisição (seção 6.2 da proposta, ADR-009)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
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
    """Dependência do FastAPI: uma `AsyncSession` por requisição.

    Commit ao fim da requisição, só quando ela não levantou exceção (REVIEW-T-10, R-01): a
    renovação de sessão e as escritas das rotas persistem sem cada rota lembrar de commitar.
    Com exceção, o `async with` fecha a sessão sem commit, e nada da requisição é gravado.
    """
    fabrica: async_sessionmaker[AsyncSession] = request.app.state.fabrica_sessoes
    async with fabrica() as sessao:
        yield sessao
        await sessao.commit()


# Escopo `function`: o commit roda ao fim da função da rota, antes da resposta ser enviada.
# Com o escopo padrão (`request`) ele roda depois do envio, e uma falha de commit vira sucesso
# para o cliente (REVIEW-T-11, R-01). Toda rota e dependência usa este alias, não `Depends` direto.
SessaoDaRequisicao = Annotated[AsyncSession, Depends(obter_sessao, scope="function")]
