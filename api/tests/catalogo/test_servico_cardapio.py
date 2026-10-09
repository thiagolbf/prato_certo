"""Cardápio vigente e leitura de item vendável (RN-08, RN-09, RN-11, RN-19, RN-50)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemForaDoCardapio, ItemVendavel, TipoCardapio
from app.catalogo.modelos import CardapioData, Formato, ItemCardapio, Prato, Proteina
from app.catalogo.repositorio import RepositorioCardapios
from app.catalogo.servico_cardapio import ServicoCardapio
from app.core.estabelecimento import estabelecimento_atual
from app.core.valores import Dinheiro

ONTEM = date(2026, 10, 7)
HOJE = date(2026, 10, 8)
AMANHA = date(2026, 10, 9)


async def _item(sessao: AsyncSession, nome_prato: str) -> ItemCardapio:
    """Prato próprio com proteína própria, e o item PF dele com preço de 18,00 e 150 g."""
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(
        estabelecimento_id=estabelecimento_id, nome=f"Proteína de {nome_prato}"
    )
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


async def _cardapio(sessao: AsyncSession, data: date, *itens: ItemCardapio) -> CardapioData:
    cardapio = CardapioData.definir(
        estabelecimento_id=await estabelecimento_atual(sessao),
        data=data,
        itens=list(itens),
        hoje=data,
    )
    sessao.add(cardapio)
    await sessao.flush()
    return cardapio


async def _servico(sessao: AsyncSession) -> ServicoCardapio:
    repositorio = RepositorioCardapios(sessao, await estabelecimento_atual(sessao))
    return ServicoCardapio(repositorio)


async def test_CA_08_item_desativado_nao_entra_no_herdado(sessao: AsyncSession) -> None:
    itens = [await _item(sessao, f"Prato {n}") for n in range(4)]
    await _cardapio(sessao, ONTEM, *itens)
    itens[0].desativar()
    await sessao.flush()
    # Recarrega o cardápio de ontem do banco, como numa requisição real: a herança não usa a
    # memória da sessão (R-01 do REVIEW-T-20).
    sessao.expire_all()

    vigente = await (await _servico(sessao)).cardapio_vigente(HOJE)

    assert vigente.tipo is TipoCardapio.HERDADO
    assert vigente.data_origem == ONTEM
    assert len(vigente.itens) == 3
    assert itens[0].id not in [item.item_id for item in vigente.itens]


async def test_cardapio_futuro_nao_e_herdado_por_data_anterior(sessao: AsyncSession) -> None:
    de_ontem = await _item(sessao, "Feijoada")
    de_amanha = await _item(sessao, "Strogonoff")
    await _cardapio(sessao, ONTEM, de_ontem)
    await _cardapio(sessao, AMANHA, de_amanha)

    vigente = await (await _servico(sessao)).cardapio_vigente(HOJE)

    assert vigente.tipo is TipoCardapio.HERDADO
    assert vigente.data_origem == ONTEM
    assert [item.item_id for item in vigente.itens] == [de_ontem.id]


async def test_sem_cardapio_algum_vigente_e_vazio(sessao: AsyncSession) -> None:
    vigente = await (await _servico(sessao)).cardapio_vigente(HOJE)

    assert vigente.tipo is TipoCardapio.VAZIO
    assert vigente.data_origem is None
    assert vigente.itens == ()


async def test_cardapio_proprio_da_data_vence_o_herdado(sessao: AsyncSession) -> None:
    de_ontem = await _item(sessao, "Feijoada")
    de_hoje = await _item(sessao, "Strogonoff")
    await _cardapio(sessao, ONTEM, de_ontem)
    await _cardapio(sessao, HOJE, de_hoje)

    vigente = await (await _servico(sessao)).cardapio_vigente(HOJE)

    assert vigente.tipo is TipoCardapio.PROPRIO
    assert vigente.data_origem is None
    assert [item.item_id for item in vigente.itens] == [de_hoje.id]


async def test_item_desativado_depois_de_entrar_no_cardapio_nao_e_vendavel(
    sessao: AsyncSession,
) -> None:
    item = await _item(sessao, "Feijoada")
    await _cardapio(sessao, HOJE, item)
    servico = await _servico(sessao)
    assert (await servico.item_vendavel(item.id, HOJE)).item_id == item.id

    item.desativar()
    await sessao.flush()

    with pytest.raises(ItemForaDoCardapio):
        await servico.item_vendavel(item.id, HOJE)


async def test_item_fora_do_vigente_e_recusado(sessao: AsyncSession) -> None:
    no_cardapio = await _item(sessao, "Feijoada")
    fora = await _item(sessao, "Strogonoff")
    await _cardapio(sessao, HOJE, no_cardapio)
    servico = await _servico(sessao)

    with pytest.raises(ItemForaDoCardapio):
        await servico.item_vendavel(fora.id, HOJE)

    vendavel = await servico.item_vendavel(no_cardapio.id, HOJE)
    assert type(vendavel) is ItemVendavel
    assert vendavel.nome_prato == "Feijoada"
    assert vendavel.nome_proteina == "Proteína de Feijoada"
    assert vendavel.formato is Formato.PF
    assert vendavel.preco == Decimal("18.00")
    assert vendavel.gramas_por_porcao == 150
