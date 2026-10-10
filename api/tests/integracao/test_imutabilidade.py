"""Imutabilidade do histórico, ponta a ponta pela API (ADR-004, CA-09, CA-11, CA-12, CA-13).

Os cenários cruzam catálogo, vendas e relatórios: depois de vendas registradas, o cardápio, o preço,
a gramagem e o item podem mudar, e as vendas e o fechamento daquele dia não mudam. O relógio fixo
define o dia operacional: 12:00 UTC é 09:00 em São Paulo.
"""

from datetime import UTC, date, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
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

ONTEM = date(2026, 10, 7)
HOJE = date(2026, 10, 8)
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def agora(self) -> datetime:
        return self._instante


def _meio_dia(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 12, 0, tzinfo=UTC)


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
    relogio: RelogioFixo,
) -> None:
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
    sessao: AsyncSession, nome_prato: str, *, proteina: str | None = None, gramas: int = 150
) -> ItemCardapio:
    estabelecimento_id = await estabelecimento_atual(sessao)
    prot = Proteina.criar(
        estabelecimento_id=estabelecimento_id, nome=proteina or f"Proteína {nome_prato}"
    )
    sessao.add(prot)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome=nome_prato,
        proteina_id=prot.id,
        gramas_por_porcao=gramas,
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


async def _cardapio_herdado_de_ontem(sessao: AsyncSession, *itens: ItemCardapio) -> None:
    """Cardápio gravado em ONTEM: hoje, sem próprio, herda dele."""
    sessao.add(
        CardapioData.definir(
            estabelecimento_id=await estabelecimento_atual(sessao),
            data=ONTEM,
            itens=list(itens),
            hoje=ONTEM,
        )
    )
    await sessao.flush()


async def _vender(cliente: AsyncClient, item: ItemCardapio, quantidade: int, chave: str) -> int:
    resposta = await cliente.post(
        "/api/vendas",
        json={"item_id": item.id, "quantidade": quantidade, "chave_idempotencia": chave},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


async def _fechamento_dia(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, admin: Usuario, dia: date
) -> dict:
    # Fechamento é só do ADMIN: quem lê entra como ADMIN (ADR-006).
    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    resposta = await cliente.get(f"/api/fechamento/dia?data={dia.isoformat()}")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


async def _cenario_de_hoje(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> tuple[Usuario, Usuario]:
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    operador = await _usuario(sessao, "joao", Perfil.OPERADOR)
    await _entrar_como(app, cliente, sessao, operador, RelogioFixo(_meio_dia(HOJE)))
    return admin, operador


async def test_CA_09_troca_de_cardapio_preserva_vendas(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    feijoada = await _item(sessao, "Feijoada")
    strogonoff = await _item(sessao, "Strogonoff")
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    admin, _ = await _cenario_de_hoje(app, cliente, sessao)
    for n in range(12):
        await _vender(cliente, feijoada, 1, f"venda-{n}")

    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    definicao = await cliente.post(
        f"/api/cardapio/{HOJE.isoformat()}", json={"itens": [strogonoff.id]}
    )
    assert definicao.status_code == 200, definicao.text

    vigente = (await cliente.get("/api/cardapio/vigente")).json()
    assert [i["item_id"] for i in vigente["itens"]] == [strogonoff.id]
    fechamento = await _fechamento_dia(app, cliente, sessao, admin, HOJE)
    assert fechamento["total_unidades"] == 12
    minhas = (await cliente.get("/api/vendas?data=2026-10-08")).json()
    assert len(minhas["vendas"]) == 12


async def test_CA_11_reajuste_de_preco_nao_altera_venda(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    feijoada = await _item(sessao, "Feijoada")
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    admin, _ = await _cenario_de_hoje(app, cliente, sessao)
    await _vender(cliente, feijoada, 2, "antes-1")
    antes = await _fechamento_dia(app, cliente, sessao, admin, HOJE)
    assert antes["faturamento_total"] == "36.00"

    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    reajuste = await cliente.post(f"/api/itens/{feijoada.id}/preco", json={"preco": "20.00"})
    assert reajuste.status_code == 200, reajuste.text

    depois = await _fechamento_dia(app, cliente, sessao, admin, HOJE)
    assert depois["faturamento_total"] == "36.00"
    vendas = (await cliente.get("/api/vendas?data=2026-10-08")).json()["vendas"]
    assert {v["preco_unitario"] for v in vendas} == {"18.00"}
    assert {v["valor_total"] for v in vendas} == {"36.00"}

    # A venda nova usa o preço novo (RN-40, snapshot no registro).
    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    await _vender(cliente, feijoada, 1, "depois-1")
    assert (await _fechamento_dia(app, cliente, sessao, admin, HOJE))[
        "faturamento_total"
    ] == "56.00"


async def test_CA_12_alteracao_de_gramagem_nao_altera_venda(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    feijoada = await _item(sessao, "Frango xis", proteina="Frango", gramas=150)
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    admin, _ = await _cenario_de_hoje(app, cliente, sessao)
    await _vender(cliente, feijoada, 2, "gramagem-1")
    assert {
        p["proteina_nome"]: p["gramas"]
        for p in (await _fechamento_dia(app, cliente, sessao, admin, HOJE))["proteina_por_tipo"]
    } == {"Frango": 300}

    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    prato_id = feijoada.prato_id
    gramagem = await cliente.post(
        f"/api/pratos/{prato_id}/gramagem", json={"gramas_por_porcao": 180}
    )
    assert gramagem.status_code == 200, gramagem.text

    assert {
        p["proteina_nome"]: p["gramas"]
        for p in (await _fechamento_dia(app, cliente, sessao, admin, HOJE))["proteina_por_tipo"]
    } == {"Frango": 300}


async def test_CA_13_item_desativado_continua_legivel_no_historico(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    feijoada = await _item(sessao, "Feijoada")
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    # Vendas no dia anterior: o fechamento de ONTEM deve continuar mostrando o item (RN-04).
    operador = await _usuario(sessao, "joao", Perfil.OPERADOR)
    await _entrar_como(app, cliente, sessao, operador, RelogioFixo(_meio_dia(ONTEM)))
    await _vender(cliente, feijoada, 3, "ontem-1")

    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    desativacao = await cliente.post(f"/api/itens/{feijoada.id}/desativar")
    assert desativacao.status_code == 200, desativacao.text

    vigente = (await cliente.get("/api/cardapio/vigente")).json()
    assert feijoada.id not in [i["item_id"] for i in vigente["itens"]]
    fechamento = await _fechamento_dia(app, cliente, sessao, admin, ONTEM)
    assert fechamento["total_unidades"] == 3
    assert [
        (i["prato_nome"], i["formato"], i["unidades"]) for i in fechamento["unidades_por_item"]
    ] == [("Feijoada", "PF", 3)]
