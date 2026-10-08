"""Sessão no servidor: abertura, validação, renovação em uso e encerramento (RN-36, RN-39, RN-54).

Os testes de cenário usam relógio injetado: o instante avança por `RelogioFixo.avancar`,
nunca pelo relógio real. Os de rota passam pelo HTTP, com a sessão de teste (transação desfeita).
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import NaoAutenticado
from app.core.relogio import obter_relogio
from app.identidade.cli import NovaSenhaAdmin, redefinir_senha_admin
from app.identidade.dependencias import NOME_COOKIE_SESSAO, exige_admin
from app.identidade.modelos import Perfil, PoliticaDeSessao, Sessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
POLITICA = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30),
    inatividade_operador=timedelta(hours=12),
)


class RelogioFixo:
    """Relógio de teste: o instante só muda quando o teste manda (ADR-005, ADR-009)."""

    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante

    def avancar(self, decorrido: timedelta) -> None:
        self.instante += decorrido


async def _usuario(sessao: AsyncSession, login: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash("senha-de-teste"),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _servico(sessao: AsyncSession, relogio: RelogioFixo) -> ServicoSessao:
    estabelecimento_id = await estabelecimento_atual(sessao)
    return ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA,
        relogio,
    )


async def test_CA_32_sessao_do_admin_parada_expira_antes_da_do_operador(
    sessao: AsyncSession,
) -> None:
    relogio = RelogioFixo(INICIO)
    servico = await _servico(sessao, relogio)
    token_admin = await servico.abrir(await _usuario(sessao, "thiago", Perfil.ADMIN))
    token_operador = await servico.abrir(await _usuario(sessao, "joao", Perfil.OPERADOR))

    relogio.avancar(timedelta(minutes=31))

    with pytest.raises(NaoAutenticado):
        await servico.validar(token_admin)
    assert (await servico.validar(token_operador)).login == "joao"


async def test_CA_55_admin_em_uso_nao_e_deslogado(sessao: AsyncSession) -> None:
    relogio = RelogioFixo(INICIO)
    servico = await _servico(sessao, relogio)
    token = await servico.abrir(await _usuario(sessao, "thiago", Perfil.ADMIN))

    # Uso a cada 20 min: passam 60 min desde o login, mas nunca 30 sem uso.
    for _ in range(3):
        relogio.avancar(timedelta(minutes=20))
        await servico.validar(token)
    relogio.avancar(timedelta(minutes=20))

    assert (await servico.validar(token)).login == "thiago"


async def test_sessao_encerrada_e_recusada(sessao: AsyncSession) -> None:
    relogio = RelogioFixo(INICIO)
    servico = await _servico(sessao, relogio)
    token = await servico.abrir(await _usuario(sessao, "joao", Perfil.OPERADOR))
    await servico.encerrar(token)

    with pytest.raises(NaoAutenticado):
        await servico.validar(token)


async def test_usuario_desativado_recusa_sessao_aberta(sessao: AsyncSession) -> None:
    relogio = RelogioFixo(INICIO)
    servico = await _servico(sessao, relogio)
    usuario = await _usuario(sessao, "joao", Perfil.OPERADOR)
    token = await servico.abrir(usuario)

    usuario.desativar()

    with pytest.raises(NaoAutenticado):
        await servico.validar(token)


async def test_token_fica_no_banco_so_como_hash(sessao: AsyncSession) -> None:
    relogio = RelogioFixo(INICIO)
    servico = await _servico(sessao, relogio)
    token = await servico.abrir(await _usuario(sessao, "joao", Perfil.OPERADOR))

    guardados = (await sessao.scalars(select(Sessao.token_hash))).all()

    assert token not in guardados
    assert len(guardados) == 1
    assert len(guardados[0]) == 64  # SHA-256 em hexadecimal


async def test_redefinir_senha_do_admin_encerra_as_sessoes(sessao: AsyncSession) -> None:
    relogio = RelogioFixo(INICIO)
    servico = await _servico(sessao, relogio)
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    token_antigo = await servico.abrir(admin)
    token_outro_aparelho = await servico.abrir(admin)

    await redefinir_senha_admin(
        sessao, NovaSenhaAdmin(login="thiago", senha="senha-nova-123"), relogio=relogio
    )

    with pytest.raises(NaoAutenticado):
        await servico.validar(token_antigo)
    with pytest.raises(NaoAutenticado):
        await servico.validar(token_outro_aparelho)


async def test_operador_recebe_403_em_rota_de_admin(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    app.dependency_overrides[obter_relogio] = lambda: relogio

    @app.get("/teste/admin", dependencies=[Depends(exige_admin)])
    async def rota_de_admin() -> dict[str, str]:
        return {"ok": "sim"}

    servico = await _servico(sessao, relogio)
    cliente.cookies.set(
        NOME_COOKIE_SESSAO, await servico.abrir(await _usuario(sessao, "joao", Perfil.OPERADOR))
    )
    assert (await cliente.get("/teste/admin")).status_code == 403

    cliente.cookies.set(
        NOME_COOKIE_SESSAO, await servico.abrir(await _usuario(sessao, "thiago", Perfil.ADMIN))
    )
    assert (await cliente.get("/teste/admin")).status_code == 200


async def test_sem_cookie_ou_com_cookie_invalido_devolve_401(
    app: FastAPI, cliente: AsyncClient
) -> None:
    app.dependency_overrides[obter_relogio] = lambda: RelogioFixo(INICIO)

    @app.get("/teste/autenticado", dependencies=[Depends(exige_admin)])
    async def rota_autenticada() -> dict[str, str]:
        return {"ok": "sim"}

    assert (await cliente.get("/teste/autenticado")).status_code == 401

    cliente.cookies.set(NOME_COOKIE_SESSAO, "token-que-nao-existe")
    assert (await cliente.get("/teste/autenticado")).status_code == 401
