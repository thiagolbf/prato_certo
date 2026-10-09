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

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obter_configuracao
from app.core.db import criar_engine, criar_fabrica_sessoes
from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import ErroDeDominio, NaoEncontrado, RegraViolada
from app.core.relogio import Relogio, RelogioDoServidor
from app.core.schemas import ModeloEstrito
from app.identidade.dependencias import politica_da_configuracao
from app.identidade.modelos import Perfil, PoliticaDeBloqueio, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.schemas import Login, Nome
from app.identidade.senha import SenhaNova, gerar_hash
from app.identidade.servico_sessao import ServicoSessao
from app.identidade.servico_usuarios import ServicoUsuarios


class IdentidadeAdmin(ModeloEstrito):
    """Nome e login, validados antes da senha: não se digita a senha para depois recusar."""

    nome: Nome
    login: Login


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
    """Cria ADMIN pelo mesmo `ServicoUsuarios` do cadastro da API (T-13, R-02 da T-09)."""
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = _servico_usuarios(sessao, estabelecimento_id, RelogioDoServidor())
    criado = await servico.criar(
        nome=dados.nome, login=dados.login, senha=dados.senha, perfil=Perfil.ADMIN
    )
    return await sessao.get_one(Usuario, criado.id)


def _servico_usuarios(
    sessao: AsyncSession, estabelecimento_id: int, relogio: Relogio
) -> ServicoUsuarios:
    usuarios = RepositorioUsuarios(sessao, estabelecimento_id)
    sessoes = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        usuarios,
        politica_da_configuracao(obter_configuracao()),
        relogio,
    )
    configuracao = obter_configuracao()
    politica_bloqueio = PoliticaDeBloqueio(
        tentativas=configuracao.bloqueio_tentativas,
        minutos=tuple(configuracao.bloqueio_minutos),
    )
    return ServicoUsuarios(usuarios, sessoes, relogio, estabelecimento_id, politica_bloqueio)


async def redefinir_senha_admin(
    sessao: AsyncSession, dados: NovaSenhaAdmin, relogio: Relogio | None = None
) -> Usuario:
    """Só ADMIN: a senha do Operador é redefinida pelo ADMIN, na interface (RN-52).

    Encerra todas as sessões abertas do ADMIN: quem tinha a senha antiga perde o acesso (RN-53).
    """
    relogio = relogio or RelogioDoServidor()
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuarios = RepositorioUsuarios(sessao, estabelecimento_id)
    admin = await usuarios.buscar_por_login(dados.login)
    if admin is None or admin.perfil is not Perfil.ADMIN:
        raise NaoEncontrado("Nenhum ADMIN com esse login.")
    if not admin.ativo:
        # Redefinir a senha não reativa a conta; dizer que liberou seria mentira (RN-53).
        raise RegraViolada("A conta está desativada. Reative-a pela área de ADMIN antes.")
    admin.redefinir_senha(await gerar_hash(dados.senha))
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        usuarios,
        politica_da_configuracao(obter_configuracao()),
        relogio,
    )
    await servico.encerrar_todas_do_usuario(admin.id)
    await sessao.flush()
    return admin


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
        if argumentos.comando == "criar-admin":
            IdentidadeAdmin(nome=argumentos.nome, login=argumentos.login)
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
