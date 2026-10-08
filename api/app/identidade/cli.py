"""Comando técnico de ADMIN, fora da interface (RN-34, RN-53; seção 3 do PLAN-001).

A interface só cadastra Operadores. O primeiro ADMIN, um ADMIN adicional e a recuperação
da senha do ADMIN passam por aqui, executados por quem tem acesso ao servidor:

    uv run python -m app.identidade.cli criar-admin --nome "Thiago" --login thiago
    uv run python -m app.identidade.cli redefinir-senha --login thiago

A senha é sempre lida sem eco e confirmada; nunca vem por argumento, que ficaria no
histórico do shell e na lista de processos.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated

from pydantic import Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obter_configuracao
from app.core.db import criar_engine, criar_fabrica_sessoes
from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import Conflito, ErroDeDominio, NaoEncontrado
from app.core.schemas import ModeloEstrito
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import SenhaNova, gerar_hash

# Limites de texto da SPEC-UI-001 (lacuna 16), os mesmos do cadastro de Operador.
Nome = Annotated[str, Field(min_length=1, max_length=60)]
Login = Annotated[str, Field(min_length=1, max_length=30, pattern=r"^\S+$")]


class NovoAdmin(ModeloEstrito):
    nome: Nome
    login: Login
    senha: SenhaNova


class NovaSenhaAdmin(ModeloEstrito):
    login: Login
    senha: SenhaNova


class SenhasDiferentes(Exception):
    pass


async def criar_admin(sessao: AsyncSession, dados: NovoAdmin) -> Usuario:
    estabelecimento_id = await estabelecimento_atual(sessao)
    if await _buscar_por_login(sessao, estabelecimento_id, dados.login) is not None:
        raise Conflito("Já existe um usuário com esse login.")
    admin = Usuario.criar(
        estabelecimento_id=estabelecimento_id,
        nome=dados.nome,
        login=dados.login,
        senha_hash=await gerar_hash(dados.senha),
        perfil=Perfil.ADMIN,
    )
    sessao.add(admin)
    await sessao.flush()
    return admin


async def redefinir_senha_admin(sessao: AsyncSession, dados: NovaSenhaAdmin) -> Usuario:
    """Só ADMIN: a senha do Operador é redefinida pelo ADMIN, na interface (RN-52)."""
    estabelecimento_id = await estabelecimento_atual(sessao)
    admin = await _buscar_por_login(sessao, estabelecimento_id, dados.login)
    if admin is None or admin.perfil is not Perfil.ADMIN:
        raise NaoEncontrado("Nenhum ADMIN com esse login.")
    admin.redefinir_senha(await gerar_hash(dados.senha))
    await sessao.flush()
    return admin


async def _buscar_por_login(
    sessao: AsyncSession, estabelecimento_id: int, login: str
) -> Usuario | None:
    # Sem diferenciar maiúsculas, como o índice único (RN-60).
    return await sessao.scalar(
        select(Usuario).where(
            Usuario.estabelecimento_id == estabelecimento_id,
            func.lower(Usuario.login) == func.lower(login),
        )
    )


def interpretar(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.identidade.cli",
        description="Operações técnicas de ADMIN. A senha é pedida sem eco.",
    )
    comandos = parser.add_subparsers(dest="comando", required=True)
    criar = comandos.add_parser("criar-admin", help="cria o primeiro ADMIN ou um ADMIN adicional")
    criar.add_argument("--nome", required=True)
    criar.add_argument("--login", required=True)
    redefinir = comandos.add_parser(
        "redefinir-senha", help="recupera o acesso de um ADMIN e encerra o bloqueio da conta"
    )
    redefinir.add_argument("--login", required=True)
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None, ler_senha: Callable[[str], str] = getpass.getpass
) -> int:
    argumentos = interpretar(argv)
    try:
        senha = _ler_senha_confirmada(ler_senha)
        if argumentos.comando == "criar-admin":
            novo = NovoAdmin(nome=argumentos.nome, login=argumentos.login, senha=senha)
            asyncio.run(_aplicar(criar_admin, novo))
            print(f'ADMIN "{novo.login}" criado.')
        else:
            nova_senha = NovaSenhaAdmin(login=argumentos.login, senha=senha)
            asyncio.run(_aplicar(redefinir_senha_admin, nova_senha))
            print(f'Senha do ADMIN "{nova_senha.login}" redefinida; a conta está liberada.')
    except ValidationError as erro:
        # Nunca `str(erro)`: o Pydantic inclui o valor recebido, que pode ser a senha.
        for item in erro.errors(include_input=False, include_url=False):
            campo = ".".join(str(parte) for parte in item["loc"])
            print(f"{campo}: {item['msg'].removeprefix('Value error, ')}", file=sys.stderr)
        return 1
    except SenhasDiferentes:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    except ErroDeDominio as erro:
        print(erro.mensagem, file=sys.stderr)
        return 1
    return 0


def _ler_senha_confirmada(ler_senha: Callable[[str], str]) -> str:
    senha = ler_senha("Senha: ")
    if ler_senha("Repita a senha: ") != senha:
        raise SenhasDiferentes
    return senha


async def _aplicar[T](acao: Callable[[AsyncSession, T], Awaitable[Usuario]], dados: T) -> None:
    engine = criar_engine(obter_configuracao())
    try:
        async with criar_fabrica_sessoes(engine)() as sessao, sessao.begin():
            await acao(sessao, dados)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
