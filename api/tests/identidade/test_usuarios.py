"""Cadastro, lista, desativação e reativação de usuários pelo ADMIN (RN-34, RN-52, RN-60).

Todas as rotas exigem ADMIN (RN-39). O relógio é injetado, para a lista mostrar o bloqueio
só enquanto ele vale. As provas de HTTP usam a sessão de teste; o cookie volta à mão por causa
do `Secure`.
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
SENHA = "senha-do-teste"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)
POLITICA_BLOQUEIO = PoliticaDeBloqueio(tentativas=5, minutos=(1, 5, 15, 60))
ROTA = "/api/usuarios"


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante

    def avancar(self, decorrido: timedelta) -> None:
        self.instante += decorrido


async def _conta(sessao: AsyncSession, login: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash(SENHA),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _token(sessao: AsyncSession, relogio: RelogioFixo, usuario: Usuario) -> str:
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        relogio,
    )
    return await servico.abrir(usuario)


async def _entrar_como(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, relogio: RelogioFixo, usuario
) -> None:
    app.dependency_overrides[obter_relogio] = lambda: relogio
    cliente.cookies.set(NOME_COOKIE_SESSAO, await _token(sessao, relogio, usuario))


async def _admin(app, cliente, sessao, relogio) -> Usuario:
    admin = await _conta(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, relogio, admin)
    return admin


async def test_CA_65_login_repetido_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin(app, cliente, sessao, RelogioFixo(INICIO))
    await _conta(sessao, "joao", Perfil.OPERADOR)

    resposta = await cliente.post(
        ROTA, json={"nome": "Joao", "login": "JOAO", "senha": "outra-senha-123"}
    )

    assert resposta.status_code == 409


async def test_CA_66_senha_curta_e_recusada_no_cadastro(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin(app, cliente, sessao, RelogioFixo(INICIO))

    resposta = await cliente.post(ROTA, json={"nome": "Ana", "login": "ana", "senha": "1234567"})

    assert resposta.status_code == 422
    assert "8" in str(resposta.json())


async def test_cadastro_sempre_cria_operador(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin(app, cliente, sessao, RelogioFixo(INICIO))

    # Perfil no corpo é campo desconhecido: recusado, nunca aceito como ADMIN.
    recusa = await cliente.post(
        ROTA, json={"nome": "Ana", "login": "ana", "senha": SENHA, "perfil": "ADMIN"}
    )
    assert recusa.status_code == 422

    criado = await cliente.post(ROTA, json={"nome": "Ana", "login": "ana", "senha": SENHA})
    assert criado.status_code == 201
    assert criado.json()["perfil"] == "OPERADOR"


async def test_desativar_encerra_sessoes_e_impede_login(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    await _admin(app, cliente, sessao, relogio)
    joao = await _conta(sessao, "joao", Perfil.OPERADOR)
    token_joao = await _token(sessao, relogio, joao)

    resposta = await cliente.post(f"{ROTA}/{joao.id}/desativar")
    assert resposta.status_code == 200

    servico = ServicoSessao(
        RepositorioSessoes(sessao, await estabelecimento_atual(sessao)),
        RepositorioUsuarios(sessao, await estabelecimento_atual(sessao)),
        POLITICA_SESSAO,
        relogio,
    )
    with pytest.raises(NaoAutenticado):
        await servico.validar(token_joao)

    login = await cliente.post("/api/auth/login", json={"login": "joao", "senha": SENHA})
    assert login.status_code == 401


async def test_reativar_devolve_o_acesso_com_a_mesma_conta(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin(app, cliente, sessao, RelogioFixo(INICIO))
    joao = await _conta(sessao, "joao", Perfil.OPERADOR)
    await cliente.post(f"{ROTA}/{joao.id}/desativar")

    resposta = await cliente.post(f"{ROTA}/{joao.id}/reativar")

    assert resposta.status_code == 200
    login = await cliente.post("/api/auth/login", json={"login": "joao", "senha": SENHA})
    assert login.status_code == 200


async def test_lista_informa_bloqueio(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    await _admin(app, cliente, sessao, relogio)
    joao = await _conta(sessao, "joao", Perfil.OPERADOR)
    await _conta(sessao, "maria", Perfil.OPERADOR)
    for _ in range(5):
        joao.registrar_falha_login(INICIO, POLITICA_BLOQUEIO)

    resposta = await cliente.get(ROTA)
    assert resposta.status_code == 200
    por_login = {item["login"]: item for item in resposta.json()}
    # O Pydantic serializa UTC como "Z": compara o instante, não o texto.
    bloqueado = datetime.fromisoformat(por_login["joao"]["bloqueado_ate"])
    assert bloqueado == INICIO + timedelta(minutes=1)
    assert por_login["maria"]["bloqueado_ate"] is None

    # Passado o bloqueio, a lista deixa de informá-lo.
    relogio.avancar(timedelta(minutes=2))
    por_login = {item["login"]: item for item in (await cliente.get(ROTA)).json()}
    assert por_login["joao"]["bloqueado_ate"] is None


async def test_operador_recebe_403_em_todas_as_rotas_de_usuarios(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    relogio = RelogioFixo(INICIO)
    joao = await _conta(sessao, "joao", Perfil.OPERADOR)
    maria = await _conta(sessao, "maria", Perfil.OPERADOR)
    await _entrar_como(app, cliente, sessao, relogio, joao)

    assert (await cliente.get(ROTA)).status_code == 403
    assert (
        await cliente.post(ROTA, json={"nome": "Ana", "login": "ana", "senha": SENHA})
    ).status_code == 403
    assert (await cliente.post(f"{ROTA}/{maria.id}/desativar")).status_code == 403
    assert (await cliente.post(f"{ROTA}/{maria.id}/reativar")).status_code == 403


async def test_corrida_no_cadastro_vira_conflito(sessao: AsyncSession) -> None:
    """Dois cadastros com o mesmo login: o índice único recusa o segundo, e vira 409."""
    from app.core.excecoes import Conflito
    from app.identidade.repositorio import RepositorioUsuarios
    from app.identidade.servico_usuarios import ServicoUsuarios

    await _conta(sessao, "joao", Perfil.OPERADOR)
    relogio = RelogioFixo(INICIO)
    estabelecimento_id = await estabelecimento_atual(sessao)

    class RepositorioSemChecagem(RepositorioUsuarios):
        # Simula a janela entre a checagem e o insert: outro cadastro já entrou.
        async def buscar_por_login(self, login: str) -> None:
            return None

    usuarios = RepositorioSemChecagem(sessao, estabelecimento_id)
    sessoes = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id), usuarios, POLITICA_SESSAO, relogio
    )
    servico = ServicoUsuarios(usuarios, sessoes, relogio, estabelecimento_id, POLITICA_BLOQUEIO)

    with pytest.raises(Conflito):
        async with sessao.begin_nested():
            await servico.criar(nome="Joao", login="JOAO", senha=SENHA, perfil=Perfil.OPERADOR)


async def test_admin_nao_desativa_a_propria_conta(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    admin = await _admin(app, cliente, sessao, RelogioFixo(INICIO))

    resposta = await cliente.post(f"{ROTA}/{admin.id}/desativar")

    assert resposta.status_code == 422
    await sessao.refresh(admin)
    assert admin.ativo is True


async def test_cadastro_recusa_senha_acima_de_72_bytes(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin(app, cliente, sessao, RelogioFixo(INICIO))

    resposta = await cliente.post(ROTA, json={"nome": "Ana", "login": "ana", "senha": "a" * 73})

    assert resposta.status_code == 422
    assert "72 bytes" in str(resposta.json())
