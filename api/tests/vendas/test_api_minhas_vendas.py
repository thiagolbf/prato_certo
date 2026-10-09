"""Lista das próprias vendas do dia: GET /api/vendas/minhas (RN-27, RN-40, RN-42; ADR-005).

O dia operacional sai do relógio do servidor. 12:00 UTC é 09:00 em São Paulo, dia 08/10.
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

REGISTRO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
HOJE = date(2026, 10, 8)
ROTA_VENDAS = "/api/vendas"
ROTA_MINHAS = f"{ROTA_VENDAS}/minhas"
CAMPOS_ESPERADOS = {
    "id",
    "horario",
    "prato_nome",
    "proteina_nome",
    "formato",
    "quantidade",
    "cancelada",
}
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
    app: FastAPI,
    cliente: AsyncClient,
    sessao: AsyncSession,
    usuario: Usuario,
    instante: datetime = REGISTRO,
) -> None:
    relogio = RelogioFixo(instante)
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


async def _registrar(
    app: FastAPI,
    cliente: AsyncClient,
    sessao: AsyncSession,
    operador: Usuario,
    item: ItemCardapio,
    quantidade: int,
    prefixo_chave: str,
    instante: datetime = REGISTRO,
) -> list[int]:
    """Registra `quantidade` vendas, uma por chave, e devolve os ids."""
    await _entrar_como(app, cliente, sessao, operador, instante)
    ids = []
    for indice in range(quantidade):
        resposta = await cliente.post(
            ROTA_VENDAS,
            json={
                "item_id": item.id,
                "quantidade": 1,
                "chave_idempotencia": f"{prefixo_chave}-{indice}",
            },
        )
        assert resposta.status_code == 201
        ids.append(resposta.json()["id"])
    return ids


async def test_CA_36_operador_ve_so_as_proprias_vendas_sem_valores(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    eu = await _usuario(sessao, "eu", Perfil.OPERADOR)
    outro = await _usuario(sessao, "outro", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    minhas = await _registrar(app, cliente, sessao, eu, item, 12, "eu")
    await _registrar(app, cliente, sessao, outro, item, 8, "outro")
    await _entrar_como(app, cliente, sessao, eu)

    resposta = await cliente.get(ROTA_MINHAS)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 12
    assert {venda["id"] for venda in corpo} == set(minhas)
    for venda in corpo:
        # Contrato sem valor: nenhum campo de preço, valor ou total monetário (RN-40).
        assert set(venda) == CAMPOS_ESPERADOS
        assert not any("preco" in campo or "valor" in campo for campo in venda)


async def test_CA_54_operador_ve_a_venda_cancelada_marcada(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    ids = await _registrar(app, cliente, sessao, operador, item, 3, "cancelada")
    await _entrar_como(app, cliente, sessao, admin)
    cancelamento = await cliente.post(
        f"{ROTA_VENDAS}/{ids[1]}/cancelar", json={"motivo": "Lançamento errado"}
    )
    assert cancelamento.status_code == 200
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.get(ROTA_MINHAS)

    assert resposta.status_code == 200
    marcadas = {venda["id"]: venda["cancelada"] for venda in resposta.json()}
    assert marcadas == {ids[0]: False, ids[1]: True, ids[2]: False}


async def test_lista_vem_da_mais_recente_e_no_horario_de_sao_paulo(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    cedo = await _registrar(app, cliente, sessao, operador, item, 1, "cedo", REGISTRO)
    tarde = await _registrar(
        app, cliente, sessao, operador, item, 1, "tarde", REGISTRO + timedelta(hours=2)
    )
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.get(ROTA_MINHAS)

    corpo = resposta.json()
    assert [venda["id"] for venda in corpo] == [tarde[0], cedo[0]]
    # 14:00 UTC é 11:00 em São Paulo (UTC-3), no fuso do dia operacional.
    assert corpo[0]["horario"].startswith("2026-10-08T11:00:00")
    assert corpo[0]["horario"].endswith("-03:00")


async def test_venda_de_outro_dia_operacional_nao_aparece(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    await _registrar(app, cliente, sessao, operador, item, 2, "ontem")
    # Hoje é 09/10 no relógio do servidor: as vendas de 08/10 ficam fora da lista.
    await _entrar_como(app, cliente, sessao, operador, REGISTRO + timedelta(days=1))

    resposta = await cliente.get(ROTA_MINHAS)

    assert resposta.status_code == 200
    assert resposta.json() == []
