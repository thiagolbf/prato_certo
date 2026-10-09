"""Consulta do cardápio pela API: vigente para o Operador, por data para o ADMIN (RN-08, RN-09,
RN-11, RN-42, RN-50). Nenhuma rota grava cardápio; o cookie volta à mão por causa do `Secure`.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import CardapioData, Formato, ItemCardapio, Prato, Proteina, cardapio_item
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

# 12:00 UTC é 09:00 em São Paulo: o dia operacional é 08/10.
INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
ONTEM = date(2026, 10, 7)
HOJE = date(2026, 10, 8)
ROTA = "/api/cardapio"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


class RelogioFixo:
    def __init__(self, instante: datetime = INICIO) -> None:
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


async def _cardapio(sessao: AsyncSession, data: date, *itens: ItemCardapio) -> None:
    sessao.add(
        CardapioData.definir(
            estabelecimento_id=await estabelecimento_atual(sessao),
            data=data,
            itens=list(itens),
            hoje=data,
        )
    )
    await sessao.flush()


async def _contagens(sessao: AsyncSession) -> tuple[int, int]:
    cardapios = await sessao.scalar(select(func.count()).select_from(CardapioData))
    vinculos = await sessao.scalar(select(func.count()).select_from(cardapio_item))
    return cardapios, vinculos


async def test_CA_07_cardapio_herdado_e_exibido_sem_gravar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    itens = [await _item(sessao, f"Prato {n}") for n in range(4)]
    await _cardapio(sessao, ONTEM, *itens)
    await _entrar_como(app, cliente, sessao, await _usuario(sessao, "joao", Perfil.OPERADOR))
    antes = await _contagens(sessao)

    resposta = await cliente.get(f"{ROTA}/vigente")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "HERDADO"
    assert corpo["data"] == "2026-10-08"
    assert corpo["data_origem"] == "2026-10-07"
    assert len(corpo["itens"]) == 4
    assert {item["item_id"] for item in corpo["itens"]} == {item.id for item in itens}
    assert Decimal(corpo["itens"][0]["preco"]) == Decimal("18.00")
    assert await _contagens(sessao) == antes


async def test_CA_10_primeiro_uso_devolve_estado_vazio(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _entrar_como(app, cliente, sessao, await _usuario(sessao, "joao", Perfil.OPERADOR))

    resposta = await cliente.get(f"{ROTA}/vigente")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "data": "2026-10-08",
        "tipo": "VAZIO",
        "data_origem": None,
        "itens": [],
    }


async def test_vigente_traz_dia_operacional_do_servidor(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    # 02:30 UTC de 09/10 é 23:30 de 08/10 em São Paulo: o dia é 08/10, não 09/10.
    relogio = RelogioFixo(datetime(2026, 10, 9, 2, 30, tzinfo=UTC))
    await _entrar_como(
        app, cliente, sessao, await _usuario(sessao, "joao", Perfil.OPERADOR), relogio
    )

    resposta = await cliente.get(f"{ROTA}/vigente")

    assert resposta.json()["data"] == "2026-10-08"


async def test_vigente_exige_sessao(cliente: AsyncClient) -> None:
    resposta = await cliente.get(f"{ROTA}/vigente")

    assert resposta.status_code == 401


async def test_admin_consulta_cardapio_da_data_e_ve_que_ela_passou(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _cardapio(sessao, ONTEM, await _item(sessao, "Feijoada"))
    await _entrar_como(app, cliente, sessao, await _usuario(sessao, "thiago", Perfil.ADMIN))

    passado = await cliente.get(ROTA, params={"data": "2026-10-07"})
    hoje = await cliente.get(ROTA, params={"data": "2026-10-08"})

    assert passado.status_code == 200
    assert passado.json()["passada"] is True
    assert passado.json()["tipo"] == "PROPRIO"
    assert len(passado.json()["itens"]) == 1
    assert hoje.json()["passada"] is False
    assert hoje.json()["tipo"] == "HERDADO"


async def test_operador_recebe_403_em_cardapio_por_data(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _entrar_como(app, cliente, sessao, await _usuario(sessao, "joao", Perfil.OPERADOR))

    resposta = await cliente.get(ROTA, params={"data": "2026-10-08"})

    assert resposta.status_code == 403
