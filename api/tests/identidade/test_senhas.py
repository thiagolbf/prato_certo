"""Redefinição de senha de operador pelo ADMIN e troca da própria senha (RN-52, RN-53, RN-60).

A redefinição zera o bloqueio e encerra as sessões do operador. A troca exige a senha atual,
conta as falhas como o login (RN-37) e encerra as outras sessões do ADMIN, mantendo a atual.
As rotas são só de ADMIN (RN-39). O cookie volta à mão por causa do `Secure`.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import NaoAutenticado
from app.core.relogio import obter_relogio
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeBloqueio, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
SENHA_ANTIGA = "senha-antiga-123"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)
POLITICA_BLOQUEIO = PoliticaDeBloqueio(tentativas=5, minutos=(1, 5, 15, 60))


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante


async def _conta(sessao: AsyncSession, login: str, perfil: Perfil, senha: str) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash(senha),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


def _servico(sessao: AsyncSession, estabelecimento_id: int, relogio: RelogioFixo) -> ServicoSessao:
    return ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        relogio,
    )


async def _admin_logado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, relogio: RelogioFixo
) -> tuple[Usuario, str]:
    app.dependency_overrides[obter_relogio] = lambda: relogio
    admin = await _conta(sessao, "thiago", Perfil.ADMIN, "senha-do-admin")
    token = await _servico(sessao, await estabelecimento_atual(sessao), relogio).abrir(admin)
    cliente.cookies.set(NOME_COOKIE_SESSAO, token)
    return admin, token


async def _entrar(cliente: AsyncClient, login: str, senha: str) -> int:
    return (
        await cliente.post("/api/auth/login", json={"login": login, "senha": senha})
    ).status_code


async def test_CA_51_redefinicao_libera_operador_bloqueado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao, RelogioFixo(INICIO))
    joao = await _conta(sessao, "joao", Perfil.OPERADOR, SENHA_ANTIGA)
    for _ in range(5):
        assert await _entrar(cliente, "joao", "senha-errada") == 401
    assert await _entrar(cliente, "joao", SENHA_ANTIGA) == 401  # bloqueado

    # O ADMIN redefine; o cookie do ADMIN volta a ser o da sessão dele.
    token_admin = cliente.cookies[NOME_COOKIE_SESSAO]
    cliente.cookies.set(NOME_COOKIE_SESSAO, token_admin)
    resposta = await cliente.post(
        f"/api/usuarios/{joao.id}/redefinir-senha", json={"senha": "senha-nova-456"}
    )
    assert resposta.status_code == 200

    assert await _entrar(cliente, "joao", "senha-nova-456") == 200
    assert await _entrar(cliente, "joao", SENHA_ANTIGA) == 401
    await sessao.refresh(joao)
    assert joao.bloqueado_ate is None


async def test_CA_52_troca_exige_senha_atual(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao, RelogioFixo(INICIO))

    errada = await cliente.post(
        "/api/conta/senha",
        json={"senha_atual": "senha-errada-1", "senha_nova": "senha-nova-456"},
    )
    assert errada.status_code == 422
    assert await _entrar(cliente, "thiago", "senha-nova-456") == 401

    certa = await cliente.post(
        "/api/conta/senha",
        json={"senha_atual": "senha-do-admin", "senha_nova": "senha-nova-456"},
    )
    assert certa.status_code == 204
    assert await _entrar(cliente, "thiago", "senha-nova-456") == 200
    assert await _entrar(cliente, "thiago", "senha-do-admin") == 401


async def test_CA_66_senha_curta_e_recusada_na_redefinicao_e_na_troca(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao, RelogioFixo(INICIO))
    joao = await _conta(sessao, "joao", Perfil.OPERADOR, SENHA_ANTIGA)

    redefinicao = await cliente.post(
        f"/api/usuarios/{joao.id}/redefinir-senha", json={"senha": "1234567"}
    )
    troca = await cliente.post(
        "/api/conta/senha", json={"senha_atual": "senha-do-admin", "senha_nova": "1234567"}
    )

    assert redefinicao.status_code == 422
    assert troca.status_code == 422


async def test_troca_encerra_as_outras_sessoes_do_admin(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    admin, token_atual = await _admin_logado(app, cliente, sessao, relogio)
    token_outro_aparelho = await _servico(
        sessao, await estabelecimento_atual(sessao), relogio
    ).abrir(admin)

    resposta = await cliente.post(
        "/api/conta/senha",
        json={"senha_atual": "senha-do-admin", "senha_nova": "senha-nova-456"},
    )
    assert resposta.status_code == 204

    servico = _servico(sessao, await estabelecimento_atual(sessao), relogio)
    with pytest.raises(NaoAutenticado):
        await servico.validar(token_outro_aparelho)
    assert (await servico.validar(token_atual)).login == "thiago"


async def test_operador_recebe_403_na_troca_e_na_redefinicao(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    app.dependency_overrides[obter_relogio] = lambda: relogio
    joao = await _conta(sessao, "joao", Perfil.OPERADOR, SENHA_ANTIGA)
    maria = await _conta(sessao, "maria", Perfil.OPERADOR, SENHA_ANTIGA)
    token = await _servico(sessao, await estabelecimento_atual(sessao), relogio).abrir(joao)
    cliente.cookies.set(NOME_COOKIE_SESSAO, token)

    assert (
        await cliente.post(
            "/api/conta/senha",
            json={"senha_atual": SENHA_ANTIGA, "senha_nova": "senha-nova-456"},
        )
    ).status_code == 403
    assert (
        await cliente.post(
            f"/api/usuarios/{maria.id}/redefinir-senha", json={"senha": "senha-nova-456"}
        )
    ).status_code == 403


async def test_redefinicao_nao_atinge_outro_admin(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao, RelogioFixo(INICIO))
    outro = await _conta(sessao, "ana", Perfil.ADMIN, "senha-da-ana")

    resposta = await cliente.post(
        f"/api/usuarios/{outro.id}/redefinir-senha", json={"senha": "senha-nova-456"}
    )

    assert resposta.status_code == 422


async def test_troca_com_senha_atual_errada_conta_para_o_bloqueio(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    """Cinco senhas atuais erradas bloqueiam a conta: nem a senha certa troca depois (RN-37)."""
    await _admin_logado(app, cliente, sessao, RelogioFixo(INICIO))

    for _ in range(5):
        errada = await cliente.post(
            "/api/conta/senha",
            json={"senha_atual": "senha-errada-1", "senha_nova": "senha-nova-456"},
        )
        assert errada.status_code == 422

    bloqueada = await cliente.post(
        "/api/conta/senha",
        json={"senha_atual": "senha-do-admin", "senha_nova": "senha-nova-456"},
    )
    assert bloqueada.status_code == 422
    assert await _entrar(cliente, "thiago", "senha-do-admin") == 401
