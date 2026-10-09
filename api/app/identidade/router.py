"""Rotas de autenticação: login, logout e sessão atual (RN-38, RN-54, ADR-006, ADR-009).

Routers são funções; o service vem por `Depends`. O cookie é httpOnly, Secure e SameSite=Lax,
e a alteração de estado é só por POST (RN-42).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import Configuracao
from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import Relogio, obter_relogio
from app.core.tempo import DiaOperacional
from app.identidade.dependencias import (
    NOME_COOKIE_SESSAO,
    exige_admin,
    politica_de_sessao,
    usuario_autenticado,
)
from app.identidade.modelos import Perfil, PoliticaDeBloqueio, PoliticaDeSessao
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.schemas import LoginEntrada, NovoUsuario, RespostaUsuario, UsuarioListado
from app.identidade.servico_autenticacao import MENSAGEM_RECUSA, ServicoAutenticacao
from app.identidade.servico_sessao import ServicoSessao, UsuarioAutenticado
from app.identidade.servico_usuarios import ServicoUsuarios, UsuarioLeitura

router = APIRouter(prefix="/api/auth", tags=["autenticação"])
# Todas as rotas de usuários são de ADMIN: a dependência fica no router, não em cada rota (RN-39).
router_usuarios = APIRouter(
    prefix="/api/usuarios", tags=["usuários"], dependencies=[Depends(exige_admin)]
)

COOKIE_OPCOES = {"path": "/", "httponly": True, "secure": True, "samesite": "lax"}


async def servico_sessao_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
    politica: Annotated[PoliticaDeSessao, Depends(politica_de_sessao)],
) -> ServicoSessao:
    return ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        politica,
        relogio,
    )


def politica_de_bloqueio(request: Request) -> PoliticaDeBloqueio:
    configuracao: Configuracao = request.app.state.configuracao
    return PoliticaDeBloqueio(
        tentativas=configuracao.bloqueio_tentativas,
        minutos=tuple(configuracao.bloqueio_minutos),
    )


async def servico_autenticacao_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    sessoes: Annotated[ServicoSessao, Depends(servico_sessao_da_requisicao)],
    politica: Annotated[PoliticaDeBloqueio, Depends(politica_de_bloqueio)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> ServicoAutenticacao:
    return ServicoAutenticacao(
        RepositorioUsuarios(sessao, estabelecimento_id), sessoes, politica, relogio
    )


@router.post("/login", response_model=RespostaUsuario)
async def login(
    corpo: LoginEntrada,
    resposta: Response,
    servico: Annotated[ServicoAutenticacao, Depends(servico_autenticacao_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> RespostaUsuario | JSONResponse:
    # Recusa sai como resposta, não como exceção: a falha de senha precisa ser gravada (RN-37).
    entrada = await servico.entrar(corpo.login, corpo.senha)
    if entrada is None:
        return JSONResponse({"detail": MENSAGEM_RECUSA}, status_code=401)
    token, usuario = entrada
    resposta.set_cookie(NOME_COOKIE_SESSAO, token, **COOKIE_OPCOES)
    return RespostaUsuario.de(usuario, DiaOperacional.corrente(relogio).data)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    sessoes: Annotated[ServicoSessao, Depends(servico_sessao_da_requisicao)],
) -> Response:
    token = request.cookies.get(NOME_COOKIE_SESSAO)
    if token:
        await sessoes.encerrar(token)
    resposta = Response(status_code=204)
    resposta.delete_cookie(NOME_COOKIE_SESSAO, **COOKIE_OPCOES)
    return resposta


@router.get("/me")
async def me(
    usuario: Annotated[UsuarioAutenticado, Depends(usuario_autenticado)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> RespostaUsuario:
    return RespostaUsuario.de(usuario, DiaOperacional.corrente(relogio).data)


async def servico_usuarios_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    sessoes: Annotated[ServicoSessao, Depends(servico_sessao_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> ServicoUsuarios:
    return ServicoUsuarios(
        RepositorioUsuarios(sessao, estabelecimento_id), sessoes, relogio, estabelecimento_id
    )


def _listado(usuario: UsuarioLeitura) -> UsuarioListado:
    return UsuarioListado(
        id=usuario.id,
        nome=usuario.nome,
        login=usuario.login,
        perfil=usuario.perfil,
        ativo=usuario.ativo,
        bloqueado_ate=usuario.bloqueado_ate,
    )


@router_usuarios.get("")
async def listar_usuarios(
    servico: Annotated[ServicoUsuarios, Depends(servico_usuarios_da_requisicao)],
) -> list[UsuarioListado]:
    return [_listado(usuario) for usuario in await servico.listar()]


@router_usuarios.post("", status_code=201)
async def cadastrar_usuario(
    corpo: NovoUsuario,
    servico: Annotated[ServicoUsuarios, Depends(servico_usuarios_da_requisicao)],
) -> UsuarioListado:
    criado = await servico.criar(
        nome=corpo.nome, login=corpo.login, senha=corpo.senha, perfil=Perfil.OPERADOR
    )
    return _listado(criado)


@router_usuarios.post("/{usuario_id}/desativar")
async def desativar_usuario(
    usuario_id: int,
    admin: Annotated[UsuarioAutenticado, Depends(exige_admin)],
    servico: Annotated[ServicoUsuarios, Depends(servico_usuarios_da_requisicao)],
) -> UsuarioListado:
    return _listado(await servico.desativar(usuario_id, por_id=admin.id))


@router_usuarios.post("/{usuario_id}/reativar")
async def reativar_usuario(
    usuario_id: int,
    admin: Annotated[UsuarioAutenticado, Depends(exige_admin)],
    servico: Annotated[ServicoUsuarios, Depends(servico_usuarios_da_requisicao)],
) -> UsuarioListado:
    return _listado(await servico.reativar(usuario_id, por_id=admin.id))
