"""Dependências de autenticação e perfil das rotas (ADR-009, RN-39).

Autorização por perfil é dependência da rota, não da entidade: `exige_admin` vai em
`dependencies=[...]` ou como parâmetro. O usuário chega à rota já como leitura imutável.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Configuracao
from app.core.db import obter_sessao
from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import NaoAutenticado, SemPermissao
from app.core.relogio import Relogio, obter_relogio
from app.identidade.modelos import Perfil, PoliticaDeSessao
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.servico_sessao import (
    MENSAGEM_NAO_AUTENTICADO,
    ServicoSessao,
    UsuarioAutenticado,
)

NOME_COOKIE_SESSAO = "sessao"


def politica_da_configuracao(configuracao: Configuracao) -> PoliticaDeSessao:
    return PoliticaDeSessao(
        inatividade_admin=timedelta(minutes=configuracao.sessao_inatividade_admin_min),
        inatividade_operador=timedelta(minutes=configuracao.sessao_inatividade_operador_min),
    )


def politica_de_sessao(request: Request) -> PoliticaDeSessao:
    return politica_da_configuracao(request.app.state.configuracao)


async def usuario_autenticado(
    request: Request,
    sessao: Annotated[AsyncSession, Depends(obter_sessao)],
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
    politica: Annotated[PoliticaDeSessao, Depends(politica_de_sessao)],
) -> UsuarioAutenticado:
    """Lê o cookie de sessão e devolve o usuário; sem cookie válido, 401.

    O token só localiza a sessão dentro do estabelecimento único de hoje; a partir daqui,
    as rotas usam o `estabelecimento_id` do próprio usuário autenticado.
    """
    token = request.cookies.get(NOME_COOKIE_SESSAO)
    if not token:
        raise NaoAutenticado(MENSAGEM_NAO_AUTENTICADO)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        politica,
        relogio,
    )
    return await servico.validar(token)


async def exige_admin(
    usuario: Annotated[UsuarioAutenticado, Depends(usuario_autenticado)],
) -> UsuarioAutenticado:
    """Recusa o Operador com 403: nenhuma tela ou operação de ADMIN (RN-39)."""
    if usuario.perfil is not Perfil.ADMIN:
        raise SemPermissao("Esta operação é exclusiva do ADMIN.")
    return usuario
