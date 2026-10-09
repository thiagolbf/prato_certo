"""Bloqueio por conta no login: 5 falhas bloqueiam só aquela conta, com espera progressiva (RN-37).

O relógio é injetado: o instante só muda quando o teste manda. O estado do bloqueio fica nas
colunas da conta, então um bloqueio precisa sobreviver a uma leitura feita do zero no banco.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import criar_engine, criar_fabrica_sessoes
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.identidade.modelos import Perfil, PoliticaDeBloqueio, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_autenticacao import ServicoAutenticacao
from app.identidade.servico_sessao import ServicoSessao

INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
ROTA_LOGIN = "/api/auth/login"
SENHA = "segredo123"


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante

    def avancar(self, decorrido: timedelta) -> None:
        self.instante += decorrido


async def _conta(sessao: AsyncSession, login: str) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash(SENHA),
        perfil=Perfil.OPERADOR,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _entrar(cliente: AsyncClient, login: str, senha: str = SENHA) -> int:
    return (await cliente.post(ROTA_LOGIN, json={"login": login, "senha": senha})).status_code


async def _falhar(cliente: AsyncClient, login: str, vezes: int) -> None:
    for _ in range(vezes):
        assert await _entrar(cliente, login, senha="senha-errada") == 401


POLITICA_BLOQUEIO = PoliticaDeBloqueio(tentativas=5, minutos=(1, 5, 15, 60))
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


async def _servico_autenticacao(sessao: AsyncSession, relogio: RelogioFixo) -> ServicoAutenticacao:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuarios = RepositorioUsuarios(sessao, estabelecimento_id)
    sessoes = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id), usuarios, POLITICA_SESSAO, relogio
    )
    return ServicoAutenticacao(usuarios, sessoes, POLITICA_BLOQUEIO, relogio)


async def _gravar_conta_com_commit(fabrica, login: str) -> None:
    async with fabrica() as sessao, sessao.begin():
        sessao.add(
            Usuario.criar(
                estabelecimento_id=await estabelecimento_atual(sessao),
                nome=login.capitalize(),
                login=login,
                senha_hash=await gerar_hash(SENHA),
                perfil=Perfil.OPERADOR,
            )
        )


async def _apagar_com_commit(fabrica, login: str) -> None:
    async with fabrica() as sessao, sessao.begin():
        await sessao.execute(delete(Usuario).where(Usuario.login == login))


async def _ler_do_zero(sessao: AsyncSession, login: str) -> Usuario:
    """Relê a conta do banco, descartando o que a sessão tinha em memória."""
    await sessao.flush()  # grava o que está pendente antes de descartar a memória
    sessao.expunge_all()
    return (await sessao.scalars(select(Usuario).where(Usuario.login == login))).one()


async def test_CA_24_bloqueio_atinge_so_a_conta_que_errou(
    app, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    app.dependency_overrides[obter_relogio] = lambda: relogio
    await _conta(sessao, "joao")
    await _conta(sessao, "maria")

    await _falhar(cliente, "joao", vezes=5)

    # A sexta tentativa encontra a conta bloqueada, mesmo com a senha certa.
    assert await _entrar(cliente, "joao", senha=SENHA) == 401
    assert await _entrar(cliente, "maria", senha=SENHA) == 200


async def test_CA_25_bloqueio_e_progressivo(
    app, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    app.dependency_overrides[obter_relogio] = lambda: relogio
    await _conta(sessao, "joao")

    await _falhar(cliente, "joao", vezes=5)  # primeiro bloqueio: 1 min
    relogio.avancar(timedelta(minutes=1))
    await _falhar(cliente, "joao", vezes=5)  # segundo bloqueio: 5 min

    conta = await _ler_do_zero(sessao, "joao")
    assert conta.bloqueios == 2
    assert conta.bloqueado_ate == INICIO + timedelta(minutes=1) + timedelta(minutes=5)

    relogio.avancar(timedelta(minutes=4))  # ainda dentro dos 5 min
    assert await _entrar(cliente, "joao", senha=SENHA) == 401

    relogio.avancar(timedelta(minutes=2))  # passou dos 5 min
    assert await _entrar(cliente, "joao", senha=SENHA) == 200


async def test_CA_38_bloqueio_sobrevive_ao_reinicio(configuracao, engine) -> None:
    """Grava as falhas com commit de verdade, troca o engine e confere o bloqueio no banco."""
    relogio = RelogioFixo(INICIO)
    login = f"reinicio-{uuid.uuid4().hex[:8]}"
    fabrica = criar_fabrica_sessoes(engine)
    await _gravar_conta_com_commit(fabrica, login)
    try:
        for _ in range(5):
            async with fabrica() as sessao, sessao.begin():
                servico = await _servico_autenticacao(sessao, relogio)
                assert await servico.entrar(login, "senha-errada") is None

        # "Reinício": engine e sessões novos, sem nada em memória.
        novo_engine = criar_engine(configuracao)
        try:
            async with criar_fabrica_sessoes(novo_engine)() as sessao, sessao.begin():
                servico = await _servico_autenticacao(sessao, relogio)
                assert await servico.entrar(login, SENHA) is None
                conta = await _ler_do_zero(sessao, login)
                assert conta.bloqueado_ate == INICIO + timedelta(minutes=1)
        finally:
            await novo_engine.dispose()
    finally:
        await _apagar_com_commit(fabrica, login)


async def test_falhas_concorrentes_nao_se_perdem(configuracao, engine) -> None:
    """Duas tentativas erradas ao mesmo tempo contam as duas (FOR UPDATE, RN-37)."""
    relogio = RelogioFixo(INICIO)
    login = f"concorrente-{uuid.uuid4().hex[:8]}"
    fabrica = criar_fabrica_sessoes(engine)
    await _gravar_conta_com_commit(fabrica, login)

    async def tentar() -> None:
        async with fabrica() as sessao, sessao.begin():
            servico = await _servico_autenticacao(sessao, relogio)
            await servico.entrar(login, "senha-errada")

    try:
        await asyncio.gather(tentar(), tentar())

        async with fabrica() as sessao:
            conta = (await sessao.scalars(select(Usuario).where(Usuario.login == login))).one()
            assert conta.falhas_consecutivas == 2
    finally:
        await _apagar_com_commit(fabrica, login)


async def test_CA_39_login_ok_zera_o_contador(
    app, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    app.dependency_overrides[obter_relogio] = lambda: relogio
    await _conta(sessao, "joao")

    await _falhar(cliente, "joao", vezes=3)
    assert await _entrar(cliente, "joao", senha=SENHA) == 200
    assert (await _ler_do_zero(sessao, "joao")).falhas_consecutivas == 0

    # Zerado: quatro falhas agora não bloqueiam; o limite é cinco e as três antigas não contam.
    await _falhar(cliente, "joao", vezes=4)
    conta = await _ler_do_zero(sessao, "joao")
    assert conta.falhas_consecutivas == 4
    assert conta.bloqueado_ate is None
