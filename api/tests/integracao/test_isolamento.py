"""Isolamento por estabelecimento e reativação com histórico (ADR-003, RN-41, RN-47, CA-33, CA-47).

A API atende um único estabelecimento por implantação (`estabelecimento_atual`), então o isolamento
é exercido nas consultas e repositórios, que recebem o `estabelecimento_id` e filtram por ele. Um
segundo estabelecimento semeado no teste não pode aparecer em nenhuma leitura do primeiro.
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemVendavel
from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.catalogo.repositorio import RepositorioProteinas
from app.core.estabelecimento import Estabelecimento, estabelecimento_atual
from app.core.valores import Dinheiro
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import gerar_hash
from app.relatorios import consultas
from app.vendas.modelos import Venda
from app.vendas.repositorio import RepositorioVendas
from tests.integracao.test_imutabilidade import (
    HOJE,
    RelogioFixo,
    _cardapio_herdado_de_ontem,
    _entrar_como,
    _item,
    _meio_dia,
    _usuario,
    _vender,
)

INICIO_HOJE = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)
FIM_HOJE = datetime(2026, 10, 9, 3, 0, tzinfo=UTC)


async def _outro_estabelecimento(sessao: AsyncSession) -> int:
    outro = Estabelecimento(nome="Outro restaurante")
    sessao.add(outro)
    await sessao.flush()
    return outro.id


async def _venda_no_outro(sessao: AsyncSession, estabelecimento_id: int) -> None:
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome="Peixe")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Moqueca de outro",
        proteina_id=proteina.id,
        gramas_por_porcao=200,
    )
    sessao.add(prato)
    await sessao.flush()
    orm = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=Formato.PF,
        preco=Dinheiro("50.00"),
    )
    sessao.add(orm)
    await sessao.flush()
    item = ItemVendavel(
        item_id=orm.id,
        nome_prato=prato.nome,
        nome_proteina=proteina.nome,
        formato=Formato.PF,
        preco=Decimal("50.00"),
        gramas_por_porcao=200,
    )
    usuario = Usuario.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Outro",
        login="outro",
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=Perfil.OPERADOR,
    )
    sessao.add(usuario)
    await sessao.flush()
    venda = Venda.registrar(
        estabelecimento_id=estabelecimento_id,
        item=item,
        quantidade=4,
        usuario_id=usuario.id,
        chave="chave-do-outro",
        agora=datetime(2026, 10, 8, 15, 0, tzinfo=UTC),
    )
    sessao.add(venda)
    await sessao.flush()


async def test_CA_33_consulta_nunca_alcanca_outro_estabelecimento(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    # Com dois estabelecimentos a API não resolve qual é o atual (REVIEW-T-56): o isolamento
    # é verificado nas consultas e repositórios, que recebem o estabelecimento_id.
    feijoada = await _item(sessao, "Feijoada")
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    await _vender(cliente, feijoada, 2, "meu-1")

    id_meu = await estabelecimento_atual(sessao)
    id_outro = await _outro_estabelecimento(sessao)
    await _venda_no_outro(sessao, id_outro)

    # Consultas agregadas do fechamento: só o meu estabelecimento (RN-29, RN-31).
    assert await consultas.total_unidades(sessao, id_meu, INICIO_HOJE, FIM_HOJE) == 2
    assert await consultas.total_unidades(sessao, id_outro, INICIO_HOJE, FIM_HOJE) == 4
    faturamento = await consultas.faturamento_total(sessao, id_meu, INICIO_HOJE, FIM_HOJE)
    assert str(faturamento) == "36.00"
    por_item = await consultas.unidades_por_item(sessao, id_meu, INICIO_HOJE, FIM_HOJE)
    assert {linha.prato_nome for linha in por_item} == {"Feijoada"}

    # Listas e catálogo: o repositório do meu estabelecimento não enxerga o outro.
    vendas_meu = await RepositorioVendas(sessao, id_meu).listar_do_dia(INICIO_HOJE, FIM_HOJE)
    assert [v.quantidade for v in vendas_meu] == [2]
    proteinas_meu = await RepositorioProteinas(sessao, id_meu).listar(incluir_desativadas=True)
    assert "Peixe" not in {p.nome for p, _ in proteinas_meu}


async def test_CA_47_item_reativado_sem_duplicar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    feijoada = await _item(sessao, "Feijoada")
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    operador = await _usuario(sessao, "joao", Perfil.OPERADOR)
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, operador, RelogioFixo(_meio_dia(HOJE)))
    await _vender(cliente, feijoada, 3, "antes-da-desativacao")
    antes = (await cliente.get("/api/vendas/minhas")).json()

    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))
    assert (await cliente.post(f"/api/itens/{feijoada.id}/desativar")).status_code == 200
    reativacao = await cliente.post(f"/api/itens/{feijoada.id}/reativar")
    assert reativacao.status_code == 200, reativacao.text

    # Cardápio novo com o item reativado: ele entra uma vez só.
    definicao = await cliente.post(
        f"/api/cardapio/{HOJE.isoformat()}", json={"itens": [feijoada.id]}
    )
    assert definicao.status_code == 200, definicao.text
    vigente = (await cliente.get("/api/cardapio/vigente")).json()
    assert [i["item_id"] for i in vigente["itens"]] == [feijoada.id]

    # As vendas anteriores ficam iguais.
    await _entrar_como(app, cliente, sessao, operador, RelogioFixo(_meio_dia(HOJE)))
    depois = (await cliente.get("/api/vendas/minhas")).json()
    assert depois == antes
    assert len(list(await sessao.scalars(select(Venda.id).where(Venda.quantidade == 3)))) == 1
