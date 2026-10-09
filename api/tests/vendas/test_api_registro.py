"""Registro de venda pela API: POST /api/vendas (RN-13 a RN-19; ADR-004, ADR-006).

O relógio fixo define o dia operacional: 12:00 UTC é 09:00 em São Paulo, dia 08/10. O cookie
volta à mão por causa do `Secure`.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
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

HOJE_INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
HOJE = date(2026, 10, 8)
ROTA = "/api/vendas"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


class RelogioFixo:
    def __init__(self, instante: datetime = HOJE_INICIO) -> None:
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
    app: FastAPI,
    cliente: AsyncClient,
    sessao: AsyncSession,
    usuario: Usuario,
    relogio: RelogioFixo | None = None,
) -> None:
    relogio = relogio or RelogioFixo()
    app.dependency_overrides[obter_relogio] = lambda: relogio
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        relogio,
    )
    cliente.cookies.set(NOME_COOKIE_SESSAO, await servico.abrir(usuario))


async def _item(
    sessao: AsyncSession,
    nome_prato: str,
    formato: Formato,
    preco: str,
    gramas: int = 150,
) -> ItemCardapio:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Proteína {nome_prato}")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome=nome_prato,
        proteina_id=proteina.id,
        gramas_por_porcao=gramas,
    )
    sessao.add(prato)
    await sessao.flush()
    item = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=formato,
        preco=Dinheiro(preco),
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


async def _vendas_com_chave(sessao: AsyncSession, chave: str) -> int:
    return await sessao.scalar(
        select(func.count()).select_from(Venda).where(Venda.chave_idempotencia == chave)
    )


async def test_CA_01_registrar_uma_unidade(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado", Formato.PF, "18.00", gramas=150)
    await _cardapio_de_hoje(sessao, item)
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.post(
        ROTA, json={"item_id": item.id, "quantidade": 1, "chave_idempotencia": "clique-1"}
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["quantidade"] == 1
    assert corpo["prato_nome"] == "Frango grelhado"
    assert corpo["formato"] == "PF"
    assert corpo["preco_unitario"] == "18.00"
    assert corpo["valor_total"] == "18.00"
    assert corpo["proteina_total_g"] == 150
    assert corpo["cancelada_em"] is None
    gravada = await sessao.scalar(select(Venda).where(Venda.id == corpo["id"]))
    assert gravada.registrada_por == operador.id


async def test_CA_02_registrar_mais_de_uma_unidade(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado", Formato.MARMITA, "22.00", gramas=150)
    await _cardapio_de_hoje(sessao, item)
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.post(
        ROTA, json={"item_id": item.id, "quantidade": 3, "chave_idempotencia": "clique-3"}
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["quantidade"] == 3
    assert corpo["valor_total"] == "66.00"
    assert corpo["proteina_total_g"] == 450


async def test_CA_05_quantidade_acima_do_teto_e_recusada(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado", Formato.MARMITA, "22.00")
    await _cardapio_de_hoje(sessao, item)
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.post(
        ROTA, json={"item_id": item.id, "quantidade": 21, "chave_idempotencia": "clique-21"}
    )

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "A quantidade de cada lançamento vai de 1 a 20."
    assert await _vendas_com_chave(sessao, "clique-21") == 0


async def test_CA_06_item_fora_do_cardapio_de_hoje_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    fora = await _item(sessao, "Feijoada", Formato.PF, "20.00")
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.post(
        ROTA, json={"item_id": fora.id, "quantidade": 1, "chave_idempotencia": "clique-fora"}
    )

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Este item não está no cardápio de hoje."
    assert await _vendas_com_chave(sessao, "clique-fora") == 0


async def test_reenvio_devolve_200_com_a_original(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado", Formato.PF, "18.00")
    await _cardapio_de_hoje(sessao, item)
    await _entrar_como(app, cliente, sessao, operador)
    corpo = {"item_id": item.id, "quantidade": 2, "chave_idempotencia": "reenvio"}

    primeira = await cliente.post(ROTA, json=corpo)
    reenvio = await cliente.post(ROTA, json={**corpo, "quantidade": 5})

    assert primeira.status_code == 201
    assert reenvio.status_code == 200
    assert reenvio.json()["id"] == primeira.json()["id"]
    # O reenvio traz outra quantidade, e a original é a que vale (RN-18).
    assert reenvio.json()["quantidade"] == 2
    assert await _vendas_com_chave(sessao, "reenvio") == 1


async def test_sem_sessao_o_registro_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    item = await _item(sessao, "Frango grelhado", Formato.PF, "18.00")
    await _cardapio_de_hoje(sessao, item)
    app.dependency_overrides[obter_relogio] = lambda: RelogioFixo()

    resposta = await cliente.post(
        ROTA, json={"item_id": item.id, "quantidade": 1, "chave_idempotencia": "anonimo"}
    )

    assert resposta.status_code == 401
    assert await _vendas_com_chave(sessao, "anonimo") == 0


async def test_admin_tambem_registra_venda(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado", Formato.PF, "18.00")
    await _cardapio_de_hoje(sessao, item)
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.post(
        ROTA, json={"item_id": item.id, "quantidade": 1, "chave_idempotencia": "admin-1"}
    )

    assert resposta.status_code == 201
    assert Decimal(resposta.json()["valor_total"]) == Decimal("18.00")
