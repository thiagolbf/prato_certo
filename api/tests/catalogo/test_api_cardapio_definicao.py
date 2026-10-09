"""Definição do cardápio da data pela API, só ADMIN (RN-10, RN-12, RN-50, RN-57).

O relógio fixo define o dia operacional: 12:00 UTC é 09:00 em São Paulo. O cookie volta à mão
por causa do `Secure`.
"""

from datetime import UTC, date, datetime, timedelta

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

HOJE_INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
ONTEM = date(2026, 10, 7)
HOJE = date(2026, 10, 8)
AMANHA = date(2026, 10, 9)
ROTA = "/api/cardapio"
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


async def _itens_do_cardapio(sessao: AsyncSession, data: date) -> set[int]:
    cardapio = await sessao.scalar(select(CardapioData).where(CardapioData.data == data))
    if cardapio is None:
        return set()
    ids = await sessao.scalars(
        select(cardapio_item.c.item_id).where(cardapio_item.c.cardapio_id == cardapio.id)
    )
    return set(ids)


async def _contagens(sessao: AsyncSession) -> tuple[int, int]:
    cardapios = await sessao.scalar(select(func.count()).select_from(CardapioData))
    vinculos = await sessao.scalar(select(func.count()).select_from(cardapio_item))
    return cardapios, vinculos


async def _admin_logado(app: FastAPI, cliente: AsyncClient, sessao: AsyncSession) -> None:
    await _entrar_como(app, cliente, sessao, await _usuario(sessao, "thiago", Perfil.ADMIN))


async def test_CA_48_admin_monta_o_cardapio_de_amanha(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    de_hoje = [await _item(sessao, f"Hoje {n}") for n in range(2)]
    await _cardapio(sessao, HOJE, *de_hoje)
    amanha = [await _item(sessao, f"Amanhã {n}") for n in range(5)]
    await _admin_logado(app, cliente, sessao)

    resposta = await cliente.post(
        f"{ROTA}/{AMANHA.isoformat()}", json={"itens": [i.id for i in amanha]}
    )

    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "PROPRIO"
    assert len(resposta.json()["itens"]) == 5
    assert await _itens_do_cardapio(sessao, AMANHA) == {i.id for i in amanha}
    # O cardápio de hoje, que o Operador vê agora, não muda (RN-50).
    assert await _itens_do_cardapio(sessao, HOJE) == {i.id for i in de_hoje}

    # Em 09/10 o Operador vê os 5 itens, sem marca de herdado (RN-07).
    await _entrar_como(
        app,
        cliente,
        sessao,
        await _usuario(sessao, "joao", Perfil.OPERADOR),
        RelogioFixo(datetime(2026, 10, 9, 12, 0, tzinfo=UTC)),
    )
    vigente = (await cliente.get(f"{ROTA}/vigente")).json()
    assert vigente["tipo"] == "PROPRIO"
    assert vigente["data_origem"] is None
    assert len(vigente["itens"]) == 5


async def test_CA_49_cardapio_de_data_passada_nao_e_alterado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    original = [await _item(sessao, "Feijoada")]
    await _cardapio(sessao, ONTEM, *original)
    outro = await _item(sessao, "Strogonoff")
    await _admin_logado(app, cliente, sessao)

    resposta = await cliente.post(f"{ROTA}/{ONTEM.isoformat()}", json={"itens": [outro.id]})

    assert resposta.status_code == 422
    assert await _itens_do_cardapio(sessao, ONTEM) == {original[0].id}


async def test_CA_61_cardapio_sem_itens_nao_e_salvo(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    antes = await _contagens(sessao)

    resposta = await cliente.post(f"{ROTA}/{AMANHA.isoformat()}", json={"itens": []})

    assert resposta.status_code == 422
    assert await _contagens(sessao) == antes


async def test_confirmar_herdado_grava_proprio(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    itens = [await _item(sessao, "Feijoada"), await _item(sessao, "Strogonoff")]
    await _cardapio(sessao, ONTEM, *itens)
    await _admin_logado(app, cliente, sessao)

    resposta = await cliente.post(
        f"{ROTA}/{HOJE.isoformat()}", json={"itens": [i.id for i in itens]}
    )

    assert resposta.status_code == 200
    assert resposta.json()["tipo"] == "PROPRIO"
    assert resposta.json()["data_origem"] is None
    assert await _itens_do_cardapio(sessao, HOJE) == {i.id for i in itens}


async def test_redefinir_cardapio_do_dia_troca_os_itens(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    primeiro = await _item(sessao, "Feijoada")
    segundo = await _item(sessao, "Strogonoff")
    await _admin_logado(app, cliente, sessao)
    await cliente.post(f"{ROTA}/{HOJE.isoformat()}", json={"itens": [primeiro.id]})

    resposta = await cliente.post(f"{ROTA}/{HOJE.isoformat()}", json={"itens": [segundo.id]})

    assert resposta.status_code == 200
    assert await _itens_do_cardapio(sessao, HOJE) == {segundo.id}


async def test_item_desativado_nao_entra_no_cardapio_novo(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    desativado = await _item(sessao, "Feijoada")
    desativado.desativar()
    await sessao.flush()
    await _admin_logado(app, cliente, sessao)

    resposta = await cliente.post(f"{ROTA}/{AMANHA.isoformat()}", json={"itens": [desativado.id]})

    assert resposta.status_code == 422
    assert await _itens_do_cardapio(sessao, AMANHA) == set()


async def test_item_inexistente_devolve_404(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)

    resposta = await cliente.post(f"{ROTA}/{AMANHA.isoformat()}", json={"itens": [999_999]})

    assert resposta.status_code == 404


async def test_operador_recebe_403_ao_definir_cardapio(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    item = await _item(sessao, "Feijoada")
    await _entrar_como(app, cliente, sessao, await _usuario(sessao, "joao", Perfil.OPERADOR))

    resposta = await cliente.post(f"{ROTA}/{AMANHA.isoformat()}", json={"itens": [item.id]})

    assert resposta.status_code == 403
    assert await _itens_do_cardapio(sessao, AMANHA) == set()
