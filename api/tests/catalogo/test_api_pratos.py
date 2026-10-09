"""Pratos pela API: nome único, proteína ativa, desativação protegida (RN-02, RN-58, RN-59).

Todas as rotas são de ADMIN (CA-26). O cookie volta à mão por causa do `Secure`.
"""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)
ROTA = "/api/pratos"


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


async def _prato(sessao: AsyncSession, proteina: Proteina, nome: str) -> Prato:
    prato = Prato.criar(
        estabelecimento_id=proteina.estabelecimento_id,
        nome=nome,
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    sessao.add(prato)
    await sessao.flush()
    return prato


async def _admin_logado(app: FastAPI, cliente: AsyncClient, sessao: AsyncSession) -> Usuario:
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, admin)
    return admin


async def test_CA_26_operador_nao_acessa_cadastro_de_pratos(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    joao = await _usuario(sessao, "joao", Perfil.OPERADOR)
    await _entrar_como(app, cliente, sessao, joao)
    frango = await _proteina(sessao, "Frango")
    prato = await _prato(sessao, frango, "Frango grelhado")

    assert (await cliente.get(ROTA)).status_code == 403
    assert (
        await cliente.post(
            ROTA, json={"nome": "PF novo", "proteina_id": frango.id, "gramas_por_porcao": 120}
        )
    ).status_code == 403
    assert (await cliente.post(f"{ROTA}/{prato.id}/desativar")).status_code == 403


async def test_CA_63_prato_com_nome_repetido_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")
    await _prato(sessao, frango, "Frango grelhado")

    resposta = await cliente.post(
        ROTA, json={"nome": "frango grelhado", "proteina_id": frango.id, "gramas_por_porcao": 120}
    )

    assert resposta.status_code == 409


async def test_prato_com_item_ativo_nao_e_desativado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")
    prato = await _prato(sessao, frango, "Frango grelhado")
    sessao.add(
        ItemCardapio.criar(
            estabelecimento_id=prato.estabelecimento_id,
            prato_id=prato.id,
            formato=Formato.PF,
            preco=Dinheiro("18.00"),
        )
    )
    await sessao.flush()

    resposta = await cliente.post(f"{ROTA}/{prato.id}/desativar")

    assert resposta.status_code == 409
    assert "Frango grelhado - PF" in resposta.json()["detail"]
    await sessao.refresh(prato)
    assert prato.ativo is True


async def test_prato_exige_proteina_ativa(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    carne = await _proteina(sessao, "Carne", ativo=False)

    resposta = await cliente.post(
        ROTA, json={"nome": "Bife", "proteina_id": carne.id, "gramas_por_porcao": 150}
    )

    assert resposta.status_code == 422


async def test_gramagem_zero_e_recusada(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")

    resposta = await cliente.post(
        ROTA, json={"nome": "PF zero", "proteina_id": frango.id, "gramas_por_porcao": 0}
    )

    assert resposta.status_code == 422


async def test_reativar_prato_exige_proteina_ativa(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    """Reativar prato de proteína desativada criaria prato ativo sem proteína (RN-58)."""
    await _admin_logado(app, cliente, sessao)
    carne = await _proteina(sessao, "Carne")
    prato = await _prato(sessao, carne, "Bife")
    prato.desativar()
    carne.desativar()
    await sessao.flush()

    resposta = await cliente.post(f"{ROTA}/{prato.id}/reativar")

    assert resposta.status_code == 422
    await sessao.refresh(prato)
    assert prato.ativo is False


async def test_renomear_e_alterar_gramagem(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")
    prato = await _prato(sessao, frango, "PF")

    renomeado = await cliente.post(f"{ROTA}/{prato.id}/renomear", json={"nome": "PF de frango"})
    gramado = await cliente.post(f"{ROTA}/{prato.id}/gramagem", json={"gramas_por_porcao": 180})

    assert renomeado.status_code == 200
    assert renomeado.json()["nome"] == "PF de frango"
    assert gramado.status_code == 200
    assert gramado.json()["gramas_por_porcao"] == 180


async def test_renomear_para_nome_de_outro_prato_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    """Renomear colide com outro prato: recusado, como no cadastro (RN-59)."""
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")
    await _prato(sessao, frango, "Frango grelhado")
    bife = await _prato(sessao, frango, "Bife")

    resposta = await cliente.post(f"{ROTA}/{bife.id}/renomear", json={"nome": " frango GRELHADO "})

    assert resposta.status_code == 409
    await sessao.refresh(bife)
    assert bife.nome == "Bife"


async def test_nome_de_prato_desativado_indica_reativar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    frango = await _proteina(sessao, "Frango")
    prato = await _prato(sessao, frango, "PF antigo")
    prato.desativar()
    await sessao.flush()

    resposta = await cliente.post(
        ROTA, json={"nome": "pf ANTIGO", "proteina_id": frango.id, "gramas_por_porcao": 120}
    )

    assert resposta.status_code == 409
    assert "reativ" in resposta.json()["detail"].lower()
