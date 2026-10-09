"""Cancelamento de venda pela API: POST /api/vendas/{id}/cancelar, só ADMIN (RN-21, RN-42, ADR-006).

O relógio fixo define o dia operacional: 12:00 UTC é 09:00 em São Paulo, dia 08/10. O cookie
volta à mão por causa do `Secure`.
"""

from datetime import UTC, date, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import CardapioData, Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao
from app.vendas.modelos import Venda

REGISTRO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CANCELAMENTO = REGISTRO + timedelta(hours=3)
HOJE = date(2026, 10, 8)
ROTA_VENDAS = "/api/vendas"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


class RelogioFixo:
    def __init__(self, instante: datetime = REGISTRO) -> None:
        self._instante = instante

    def agora(self) -> datetime:
        return self._instante


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
    relogio = RelogioFixo()
    app.dependency_overrides[obter_relogio] = lambda: relogio
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        relogio,
    )
    cliente.cookies.set(NOME_COOKIE_SESSAO, await servico.abrir(usuario))


async def _item(sessao: AsyncSession, nome_prato: str) -> ItemCardapio:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Proteína {nome_prato}")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome=nome_prato,
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    sessao.add(prato)
    await sessao.flush()
    item = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=Formato.PF,
        preco=Dinheiro("18.00"),
    )
    sessao.add(item)
    await sessao.flush()
    return item


async def _cardapio_de_hoje(sessao: AsyncSession, *itens: ItemCardapio) -> None:
    sessao.add(
        CardapioData.definir(
            estabelecimento_id=await estabelecimento_atual(sessao),
            data=HOJE,
            itens=list(itens),
            hoje=HOJE,
        )
    )
    await sessao.flush()


async def _venda_registrada_por(
    app: FastAPI,
    cliente: AsyncClient,
    sessao: AsyncSession,
    operador: Usuario,
    item: ItemCardapio,
    chave: str,
) -> int:
    """Registra a venda pela própria API, como o Operador faria, e devolve o id."""
    await _entrar_como(app, cliente, sessao, operador)
    resposta = await cliente.post(
        ROTA_VENDAS, json={"item_id": item.id, "quantidade": 1, "chave_idempotencia": chave}
    )
    assert resposta.status_code == 201
    return resposta.json()["id"]


async def _cancelada_em(sessao: AsyncSession, venda_id: int) -> datetime | None:
    venda = await sessao.scalar(select(Venda).where(Venda.id == venda_id))
    await sessao.refresh(venda)
    return venda.cancelada_em


async def test_CA_15_operador_nao_pode_cancelar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    venda_id = await _venda_registrada_por(app, cliente, sessao, operador, item, "op-15")

    resposta = await cliente.post(
        f"{ROTA_VENDAS}/{venda_id}/cancelar", json={"motivo": "Tentativa do Operador"}
    )

    assert resposta.status_code == 403
    assert await _cancelada_em(sessao, venda_id) is None


async def test_CA_40_cancelamento_por_get_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    venda_id = await _venda_registrada_por(app, cliente, sessao, operador, item, "get-40")
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.get(f"{ROTA_VENDAS}/{venda_id}/cancelar")

    # A rota só existe em POST: um GET nunca chega a cancelar (ADR-006).
    assert resposta.status_code == 405
    assert await _cancelada_em(sessao, venda_id) is None


async def test_admin_cancela_com_motivo(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    venda_id = await _venda_registrada_por(app, cliente, sessao, operador, item, "admin-ok")
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.post(
        f"{ROTA_VENDAS}/{venda_id}/cancelar", json={"motivo": "  Lançamento errado  "}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["id"] == venda_id
    assert corpo["cancelada_em"] is not None
    venda = await sessao.scalar(select(Venda).where(Venda.id == venda_id))
    await sessao.refresh(venda)
    assert venda.cancelada_por == admin.id
    assert venda.motivo_cancelamento == "Lançamento errado"


async def test_motivo_vazio_e_recusado_com_mensagem_de_negocio(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    venda_id = await _venda_registrada_por(app, cliente, sessao, operador, item, "motivo-vazio")
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.post(f"{ROTA_VENDAS}/{venda_id}/cancelar", json={"motivo": "   "})

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Informe o motivo do cancelamento (RN-26)."
    assert await _cancelada_em(sessao, venda_id) is None


async def test_motivo_acima_de_200_caracteres_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    venda_id = await _venda_registrada_por(app, cliente, sessao, operador, item, "motivo-longo")
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.post(f"{ROTA_VENDAS}/{venda_id}/cancelar", json={"motivo": "x" * 201})

    assert resposta.status_code == 422
    assert await _cancelada_em(sessao, venda_id) is None


async def test_venda_inexistente_devolve_404(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.post(f"{ROTA_VENDAS}/999999/cancelar", json={"motivo": "Qualquer"})

    assert resposta.status_code == 404
