"""Login, logout e sessão atual pela API, com cookie httpOnly (RN-38, RN-45, RN-54, ADR-006).

Os testes falam com a rota pelo HTTP, com a sessão de teste (transação desfeita). O cookie
`Secure` não volta pelo cliente sobre `http://`, então o token é passado de volta à mão.
"""

import logging

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.estabelecimento import estabelecimento_atual
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import gerar_hash

ROTA_LOGIN = "/api/auth/login"
ROTA_LOGOUT = "/api/auth/logout"
ROTA_ME = "/api/auth/me"
MENSAGEM_RECUSA = "Usuário ou senha inválidos."


async def _conta(
    sessao: AsyncSession,
    login: str,
    senha: str = "segredo123",
    perfil: Perfil = Perfil.OPERADOR,
    ativo: bool = True,
) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash(senha),
        perfil=perfil,
    )
    if not ativo:
        usuario.desativar()
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _entrar(cliente: AsyncClient, login: str, senha: str = "segredo123"):
    return await cliente.post(ROTA_LOGIN, json={"login": login, "senha": senha})


def _autenticar(cliente: AsyncClient, token: str) -> None:
    cliente.cookies.set(NOME_COOKIE_SESSAO, token)


async def test_CA_35_erro_de_login_nao_revela_a_conta(
    cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _conta(sessao, "joao")
    await _conta(sessao, "inativo", ativo=False)

    respostas = [
        await _entrar(cliente, "ninguem"),
        await _entrar(cliente, "joao", senha="senha-errada"),
        await _entrar(cliente, "inativo"),
    ]

    for resposta in respostas:
        assert resposta.status_code == 401
        assert resposta.json() == {"detail": MENSAGEM_RECUSA}


async def test_CA_42_cookie_de_sessao_e_secure(cliente: AsyncClient, sessao: AsyncSession) -> None:
    await _conta(sessao, "joao")

    resposta = await _entrar(cliente, "joao")

    assert resposta.status_code == 200
    cookie = resposta.headers["set-cookie"].lower()
    assert f"{NOME_COOKIE_SESSAO}=" in cookie
    for atributo in ("httponly", "secure", "samesite=lax", "path=/"):
        assert atributo in cookie


async def test_CA_43_log_de_login_nao_contem_a_senha(
    cliente: AsyncClient, sessao: AsyncSession, caplog
) -> None:
    usuario = await _conta(sessao, "joao", senha="segredo123")
    hash_guardado = usuario.senha_hash
    caplog.set_level(logging.DEBUG, logger="app")

    resposta = await _entrar(cliente, "joao", senha="segredo123")
    token = resposta.cookies[NOME_COOKIE_SESSAO]
    await _entrar(cliente, "joao", senha="senha-errada")

    assert any(registro.name == "app.identidade" for registro in caplog.records)
    saida = caplog.text + repr([vars(registro) for registro in caplog.records])
    assert "segredo123" not in saida
    assert hash_guardado not in saida
    assert token not in saida


async def test_CA_56_sair_encerra_a_sessao_no_servidor(
    cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _conta(sessao, "joao")
    token = (await _entrar(cliente, "joao")).cookies[NOME_COOKIE_SESSAO]

    _autenticar(cliente, token)
    assert (await cliente.post(ROTA_LOGOUT)).status_code == 204

    _autenticar(cliente, token)  # o cookie antigo, que o navegador já removeu
    assert (await cliente.get(ROTA_ME)).status_code == 401


async def test_logout_por_get_nao_existe(cliente: AsyncClient) -> None:
    assert (await cliente.get(ROTA_LOGOUT)).status_code == 405


async def test_me_devolve_nome_perfil_e_dia_operacional(
    cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _conta(sessao, "thiago", perfil=Perfil.ADMIN)
    token = (await _entrar(cliente, "thiago")).cookies[NOME_COOKIE_SESSAO]

    _autenticar(cliente, token)
    resposta = await cliente.get(ROTA_ME)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Thiago"
    assert corpo["perfil"] == "ADMIN"
    assert len(corpo["dia_operacional"]) == 10  # AAAA-MM-DD


async def test_login_de_conta_gravada_com_senha_sem_espaco_nas_pontas(
    cliente: AsyncClient, sessao: AsyncSession
) -> None:
    # A senha chega como digitada (TextoLiteral): espaço nas pontas faz parte dela.
    await _conta(sessao, "joao", senha=" segredo123 ")
    assert (await _entrar(cliente, "joao", senha="segredo123")).status_code == 401
    assert (await _entrar(cliente, "joao", senha=" segredo123 ")).status_code == 200
