"""Comando técnico de ADMIN: criação e recuperação de acesso fora da interface (RN-34, RN-53).

Os testes de banco chamam as funções do comando com a sessão de teste (transação desfeita);
os de entrada chamam `main` com uma leitura de senha falsa, e são recusados antes do banco.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import Conflito, NaoEncontrado
from app.identidade.cli import (
    NovaSenhaAdmin,
    NovoAdmin,
    criar_admin,
    interpretar,
    main,
    redefinir_senha_admin,
)
from app.identidade.modelos import Perfil, PoliticaDeBloqueio, Usuario
from app.identidade.senha import conferir, gerar_hash

AGORA = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
POLITICA = PoliticaDeBloqueio(tentativas=5, minutos=(1, 5, 15, 60))


def _leitor(*respostas: str) -> Callable[[str], str]:
    """Imita o `getpass`: devolve as respostas em ordem e guarda os textos de pergunta."""
    fila: Iterator[str] = iter(respostas)

    def ler(_pergunta: str) -> str:
        return next(fila)

    return ler


async def _buscar(sessao: AsyncSession, login: str) -> Usuario:
    return (await sessao.scalars(select(Usuario).where(Usuario.login == login))).one()


async def _operador(sessao: AsyncSession, login: str) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome="João",
        login=login,
        senha_hash=await gerar_hash("senha-do-joao"),
        perfil=Perfil.OPERADOR,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def test_cli_cria_admin(sessao: AsyncSession) -> None:
    dados = NovoAdmin(nome="Thiago", login="thiago", senha="senha-do-thiago")

    await criar_admin(sessao, dados)

    admin = await _buscar(sessao, "thiago")
    assert admin.perfil is Perfil.ADMIN
    assert admin.ativo is True
    assert admin.nome == "Thiago"
    assert admin.estabelecimento_id == await estabelecimento_atual(sessao)
    assert admin.senha_hash != "senha-do-thiago"
    assert await conferir("senha-do-thiago", admin.senha_hash)


async def test_cli_cria_admin_adicional(sessao: AsyncSession) -> None:
    await criar_admin(sessao, NovoAdmin(nome="Thiago", login="thiago", senha="senha-do-thiago"))

    await criar_admin(sessao, NovoAdmin(nome="Ana", login="ana", senha="senha-da-ana"))

    assert (await _buscar(sessao, "ana")).perfil is Perfil.ADMIN


async def test_login_repetido_e_recusado_sem_diferenciar_maiusculas(sessao: AsyncSession) -> None:
    await _operador(sessao, "joao")

    with pytest.raises(Conflito):
        await criar_admin(sessao, NovoAdmin(nome="João", login="JOAO", senha="12345678"))


async def test_cli_redefine_senha_do_admin(sessao: AsyncSession) -> None:
    await criar_admin(sessao, NovoAdmin(nome="Thiago", login="thiago", senha="senha-antiga"))
    admin = await _buscar(sessao, "thiago")
    for _ in range(5):
        admin.registrar_falha_login(AGORA, POLITICA)
    assert admin.esta_bloqueado(AGORA)

    await redefinir_senha_admin(sessao, NovaSenhaAdmin(login="THIAGO", senha="senha-nova-123"))

    await sessao.refresh(admin)
    assert await conferir("senha-nova-123", admin.senha_hash)
    assert not await conferir("senha-antiga", admin.senha_hash)
    # Recuperar o acesso é poder entrar logo depois (RN-53, como a RN-52 para o Operador).
    assert admin.falhas_consecutivas == 0
    assert not admin.esta_bloqueado(AGORA)


async def test_redefinir_senha_nao_atinge_operador(sessao: AsyncSession) -> None:
    operador = await _operador(sessao, "joao")
    hash_anterior = operador.senha_hash

    with pytest.raises(NaoEncontrado):
        await redefinir_senha_admin(sessao, NovaSenhaAdmin(login="joao", senha="senha-nova-123"))

    assert operador.senha_hash == hash_anterior


async def test_redefinir_senha_de_login_inexistente_e_recusado(sessao: AsyncSession) -> None:
    with pytest.raises(NaoEncontrado):
        await redefinir_senha_admin(sessao, NovaSenhaAdmin(login="ninguem", senha="senha-nova-123"))


def test_senha_nao_e_aceita_por_argumento() -> None:
    # Senha em argumento ficaria no histórico do shell e na lista de processos.
    with pytest.raises(SystemExit):
        interpretar(["criar-admin", "--nome", "Ana", "--login", "ana", "--senha", "12345678"])


def test_senha_curta_e_recusada_no_comando(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = main(
        ["criar-admin", "--nome", "Ana", "--login", "ana"], ler_senha=_leitor("1234567", "1234567")
    )

    assert codigo == 1
    erro = capsys.readouterr().err
    assert "8" in erro
    assert "1234567" not in erro


def test_senha_acima_de_72_bytes_e_recusada_no_comando(capsys: pytest.CaptureFixture[str]) -> None:
    longa = "a" * 73

    codigo = main(["redefinir-senha", "--login", "ana"], ler_senha=_leitor(longa, longa))

    assert codigo == 1
    erro = capsys.readouterr().err
    assert "72 bytes" in erro
    assert longa not in erro


def test_confirmacao_diferente_e_recusada(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = main(
        ["criar-admin", "--nome", "Ana", "--login", "ana"],
        ler_senha=_leitor("senha-da-ana", "senha-da-ana!"),
    )

    assert codigo == 1
    assert "não conferem" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("nome", "login"),
    [("Ana", "ana maria"), ("Ana", "a" * 31), ("", "ana"), ("A" * 61, "ana")],
)
def test_nome_e_login_fora_dos_limites_sao_recusados(
    nome: str, login: str, capsys: pytest.CaptureFixture[str]
) -> None:
    codigo = main(
        ["criar-admin", "--nome", nome, "--login", login],
        ler_senha=_leitor("senha-da-ana", "senha-da-ana"),
    )

    assert codigo == 1
    assert "senha-da-ana" not in capsys.readouterr().err
