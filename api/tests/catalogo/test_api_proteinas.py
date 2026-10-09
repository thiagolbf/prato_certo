"""Proteínas pela API: nome único, desativação protegida e reativação (RN-01, RN-49, RN-58).

Todas as rotas são de ADMIN (o Operador recebe 403). O cookie volta à mão por causa do `Secure`.
"""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)
ROTA = "/api/proteinas"


class RelogioFixo:
    def agora(self) -> datetime:
        return INICIO


async def _usuario(sessao: AsyncSession, login: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _entrar_como(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, usuario: Usuario
) -> None:
    app.dependency_overrides[obter_relogio] = lambda: RelogioFixo()
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        RelogioFixo(),
    )
    cliente.cookies.set(NOME_COOKIE_SESSAO, await servico.abrir(usuario))


async def _proteina(sessao: AsyncSession, nome: str, ativo: bool = True) -> Proteina:
    proteina = Proteina.criar(estabelecimento_id=await estabelecimento_atual(sessao), nome=nome)
    if not ativo:
        proteina.desativar()
    sessao.add(proteina)
    await sessao.flush()
    return proteina


async def _admin_logado(app, cliente, sessao) -> Usuario:
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, admin)
    return admin


async def test_CA_29_proteina_com_nome_repetido_e_recusada(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    await _proteina(sessao, "Frango")

    resposta = await cliente.post(ROTA, json={"nome": " frango "})

    assert resposta.status_code == 409


async def test_nome_de_desativada_indica_reativar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    await _proteina(sessao, "Carne", ativo=False)

    resposta = await cliente.post(ROTA, json={"nome": "carne"})

    assert resposta.status_code == 409
    assert "reativ" in resposta.json()["detail"].lower()


async def test_CA_62_proteina_em_uso_nao_e_desativada(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")
    sessao.add(
        Prato.criar(
            estabelecimento_id=frango.estabelecimento_id,
            nome="Frango grelhado",
            proteina_id=frango.id,
            gramas_por_porcao=150,
        )
    )
    await sessao.flush()

    resposta = await cliente.post(f"{ROTA}/{frango.id}/desativar")

    assert resposta.status_code == 409
    assert "Frango grelhado" in resposta.json()["detail"]
    await sessao.refresh(frango)
    assert frango.ativo is True


async def test_reativar_proteina(app: FastAPI, cliente: AsyncClient, sessao: AsyncSession) -> None:
    await _admin_logado(app, cliente, sessao)
    ovo = await _proteina(sessao, "Ovo")

    desativada = await cliente.post(f"{ROTA}/{ovo.id}/desativar")
    assert desativada.status_code == 200
    assert desativada.json()["ativo"] is False

    reativada = await cliente.post(f"{ROTA}/{ovo.id}/reativar")
    assert reativada.status_code == 200
    assert reativada.json() == {"id": ovo.id, "nome": "Ovo", "ativo": True, "pratos_ativos": 0}


async def test_listagem_oculta_desativadas_por_padrao(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    await _proteina(sessao, "Peixe")
    await _proteina(sessao, "Tofu", ativo=False)

    padrao = (await cliente.get(ROTA)).json()
    completa = (await cliente.get(ROTA, params={"incluir_desativadas": "true"})).json()

    assert [item["nome"] for item in padrao] == ["Peixe"]
    assert sorted(item["nome"] for item in completa) == ["Peixe", "Tofu"]


async def test_operador_recebe_403(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    joao = await _usuario(sessao, "joao", Perfil.OPERADOR)
    await _entrar_como(app, cliente, sessao, joao)
    ovo = await _proteina(sessao, "Ovo")

    assert (await cliente.get(ROTA)).status_code == 403
    assert (await cliente.post(ROTA, json={"nome": "Peixe"})).status_code == 403
    assert (await cliente.post(f"{ROTA}/{ovo.id}/desativar")).status_code == 403


async def test_renomear_para_nome_de_outra_proteina_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    """Renomear colide com outra proteína do estabelecimento: recusado, como no cadastro (RN-01)."""
    await _admin_logado(app, cliente, sessao)
    await _proteina(sessao, "Frango")
    carne = await _proteina(sessao, "Carne")

    resposta = await cliente.post(f"{ROTA}/{carne.id}/renomear", json={"nome": " frango "})

    assert resposta.status_code == 409
    await sessao.refresh(carne)
    assert carne.nome == "Carne"


async def test_renomear_mantendo_o_proprio_nome_e_aceito(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    """O próprio registro não colide consigo: trocar só a caixa do nome é uma renomeação válida."""
    await _admin_logado(app, cliente, sessao)
    carne = await _proteina(sessao, "carne")

    resposta = await cliente.post(f"{ROTA}/{carne.id}/renomear", json={"nome": "Carne"})

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Carne"


async def test_renomear_para_branco_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    carne = await _proteina(sessao, "Carne")

    resposta = await cliente.post(f"{ROTA}/{carne.id}/renomear", json={"nome": "   "})

    assert resposta.status_code == 422
