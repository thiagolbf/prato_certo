"""Entidade Usuario: perfil, desativação e bloqueio progressivo por conta (RN-34, RN-37, RN-60).

A regra mora na entidade (ADR-009); o login que a usa é da T-12.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.estabelecimento import Estabelecimento
from app.identidade.modelos import Perfil, PoliticaDeBloqueio, Usuario

AGORA = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
POLITICA = PoliticaDeBloqueio(tentativas=5, minutos=(1, 5, 15, 60))


def _usuario(login: str = "joao", estabelecimento_id: int = 1) -> Usuario:
    return Usuario.criar(
        estabelecimento_id=estabelecimento_id,
        nome="João",
        login=login,
        senha_hash="$2b$12$hash-de-teste",
        perfil=Perfil.OPERADOR,
    )


def _errar(usuario: Usuario, vezes: int, agora: datetime = AGORA) -> None:
    for _ in range(vezes):
        usuario.registrar_falha_login(agora, POLITICA)


def test_usuario_novo_esta_ativo_sem_falhas_nem_bloqueio() -> None:
    usuario = _usuario()

    assert usuario.ativo is True
    assert usuario.falhas_consecutivas == 0
    assert usuario.bloqueios == 0
    assert usuario.bloqueado_ate is None
    assert not usuario.esta_bloqueado(AGORA)


def test_quarta_falha_ainda_nao_bloqueia() -> None:
    usuario = _usuario()

    _errar(usuario, 4)

    assert usuario.falhas_consecutivas == 4
    assert not usuario.esta_bloqueado(AGORA)


def test_quinta_falha_bloqueia_por_um_minuto() -> None:
    usuario = _usuario()

    _errar(usuario, 5)

    assert usuario.bloqueado_ate == AGORA + timedelta(minutes=1)
    assert usuario.esta_bloqueado(AGORA + timedelta(seconds=59))
    assert not usuario.esta_bloqueado(AGORA + timedelta(minutes=1))
    # O contador recomeça: o próximo bloqueio exige outras 5 falhas.
    assert usuario.falhas_consecutivas == 0
    assert usuario.bloqueios == 1


def test_bloqueio_e_progressivo_ate_o_teto() -> None:
    usuario = _usuario()
    instante = AGORA
    duracoes = []

    for _ in range(6):
        _errar(usuario, 5, instante)
        assert usuario.bloqueado_ate is not None
        duracoes.append(usuario.bloqueado_ate - instante)
        instante = usuario.bloqueado_ate  # tenta de novo quando o bloqueio acaba

    assert duracoes == [timedelta(minutes=m) for m in (1, 5, 15, 60, 60, 60)]
    assert usuario.bloqueios == 6


def test_falha_durante_bloqueio_nao_conta() -> None:
    """Tentativa com a conta bloqueada não chega a conferir senha: não escala o bloqueio.

    Sem isso, quem digitasse errado numa conta alheia a levaria ao teto em segundos.
    """
    usuario = _usuario()
    _errar(usuario, 5)

    _errar(usuario, 15, AGORA + timedelta(seconds=30))

    assert usuario.bloqueado_ate == AGORA + timedelta(minutes=1)
    assert usuario.bloqueios == 1
    assert usuario.falhas_consecutivas == 0


def test_falha_logo_depois_do_bloqueio_volta_a_contar() -> None:
    usuario = _usuario()
    _errar(usuario, 5)

    _errar(usuario, 1, AGORA + timedelta(minutes=1))

    assert usuario.falhas_consecutivas == 1


def test_login_ok_zera_falhas() -> None:
    usuario = _usuario()
    _errar(usuario, 3)

    usuario.registrar_login_ok()

    assert usuario.falhas_consecutivas == 0
    _errar(usuario, 4)
    assert not usuario.esta_bloqueado(AGORA)  # as 3 de antes não contam mais


def test_login_ok_nao_reinicia_a_progressao_dos_bloqueios() -> None:
    """A RN-37 zera o contador de falhas; não diz que a progressão volta ao início."""
    usuario = _usuario()
    _errar(usuario, 5)
    depois = AGORA + timedelta(minutes=1)

    usuario.registrar_login_ok()
    _errar(usuario, 5, depois)

    assert usuario.bloqueado_ate == depois + timedelta(minutes=5)


def test_redefinir_senha_troca_o_hash_e_encerra_o_bloqueio() -> None:
    """Quem teve a senha redefinida volta a entrar sem esperar (RN-52, RN-53)."""
    usuario = _usuario()
    _errar(usuario, 5)
    _errar(usuario, 2, AGORA + timedelta(minutes=1))
    _errar(usuario, 3, AGORA + timedelta(minutes=1))

    usuario.redefinir_senha("$2b$12$hash-novo")

    assert usuario.senha_hash == "$2b$12$hash-novo"
    assert usuario.falhas_consecutivas == 0
    assert usuario.bloqueado_ate is None
    assert not usuario.esta_bloqueado(AGORA + timedelta(minutes=1))


def test_esta_bloqueado_exige_instante_com_fuso() -> None:
    usuario = _usuario()

    with pytest.raises(ValueError, match="fuso"):
        usuario.esta_bloqueado(datetime(2026, 9, 22, 14, 0))


def test_desativar_e_reativar_nao_apagam() -> None:
    usuario = _usuario()

    usuario.desativar()
    assert usuario.ativo is False
    assert usuario.login == "joao"  # a conta continua lá, com a autoria das vendas (RN-34)

    usuario.reativar()
    assert usuario.ativo is True


@pytest.mark.parametrize(("tentativas", "minutos"), [(0, (1,)), (5, ()), (5, (1, 0)), (5, (1, -5))])
def test_politica_de_bloqueio_invalida_e_recusada(
    tentativas: int, minutos: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError):
        PoliticaDeBloqueio(tentativas=tentativas, minutos=minutos)


async def _estabelecimento_semeado(sessao: AsyncSession) -> int:
    return await sessao.scalar(select(Estabelecimento.id))  # type: ignore[return-value]


async def test_estado_de_bloqueio_fica_nas_colunas_da_conta(sessao: AsyncSession) -> None:
    """Não é memória de processo: relido do banco, o bloqueio continua lá (RN-37)."""
    usuario = _usuario(estabelecimento_id=await _estabelecimento_semeado(sessao))
    sessao.add(usuario)
    _errar(usuario, 5)
    _errar(usuario, 2, AGORA + timedelta(minutes=1))  # depois do fim do bloqueio
    await sessao.flush()
    sessao.expunge(usuario)

    relido = await sessao.scalar(select(Usuario).where(Usuario.id == usuario.id))

    assert relido is not None
    assert relido.bloqueado_ate == AGORA + timedelta(minutes=1)
    assert relido.falhas_consecutivas == 2
    assert relido.bloqueios == 1
    assert relido.perfil is Perfil.OPERADOR


async def test_login_unico_sem_diferenciar_maiusculas(sessao: AsyncSession) -> None:
    estabelecimento_id = await _estabelecimento_semeado(sessao)
    sessao.add(_usuario("Joao", estabelecimento_id))
    await sessao.flush()

    sessao.add(_usuario("jOAO", estabelecimento_id))
    with pytest.raises(IntegrityError, match="uq_usuario_estabelecimento_id_login"):
        await sessao.flush()


async def test_mesmo_login_em_outro_estabelecimento_e_permitido(sessao: AsyncSession) -> None:
    """A unicidade é no estabelecimento (RN-60, ADR-003)."""
    primeiro = await _estabelecimento_semeado(sessao)
    outro = await sessao.scalar(
        insert(Estabelecimento).values(nome="Outro restaurante").returning(Estabelecimento.id)
    )
    sessao.add_all([_usuario("joao", primeiro), _usuario("joao", outro)])  # type: ignore[arg-type]

    await sessao.flush()
