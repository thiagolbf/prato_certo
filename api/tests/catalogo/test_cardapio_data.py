"""Cardápio da data: definição própria e herança resolvida em memória (RN-07, RN-08, RN-12, RN-57).

O cardápio herdado é um objeto em memória: nunca entra na sessão e nada é gravado ao herdar.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import CardapioData, Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import RegraViolada
from app.core.valores import Dinheiro

ONTEM = date(2026, 10, 7)
HOJE = date(2026, 10, 8)


def _item(prato_id: int = 1, formato: Formato = Formato.PF, ativo: bool = True) -> ItemCardapio:
    item = ItemCardapio.criar(
        estabelecimento_id=1, prato_id=prato_id, formato=formato, preco=Dinheiro("18.00")
    )
    if not ativo:
        item.desativar()
    return item


def _cardapio_de(data: date, *itens: ItemCardapio) -> CardapioData:
    return CardapioData.definir(estabelecimento_id=1, data=data, itens=list(itens))


def test_cardapio_vazio_e_recusado() -> None:
    with pytest.raises(RegraViolada):
        CardapioData.definir(estabelecimento_id=1, data=HOJE, itens=[])


def test_item_desativado_nao_entra_em_cardapio_novo() -> None:
    with pytest.raises(RegraViolada):
        _cardapio_de(HOJE, _item(ativo=False))


def test_herdado_descarta_item_desativado() -> None:
    ativo = _item(prato_id=1)
    desativado = _item(prato_id=2, ativo=False)
    anterior = CardapioData(estabelecimento_id=1, data=ONTEM, itens=[ativo, desativado])

    herdado = CardapioData.herdar_de(anterior, HOJE)

    assert herdado.itens == [ativo]


def test_herdado_guarda_data_de_origem() -> None:
    anterior = _cardapio_de(ONTEM, _item())

    herdado = CardapioData.herdar_de(anterior, HOJE)

    assert herdado.herdado is True
    assert herdado.data_origem == ONTEM
    assert herdado.data == HOJE


async def test_herdar_nao_grava_nada_no_banco(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome="Carne cardápio")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Bife cardápio",
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    sessao.add(prato)
    await sessao.flush()
    item = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=Formato.PF,
        preco=Dinheiro("20.00"),
    )
    sessao.add(item)
    await sessao.flush()
    anterior = CardapioData.definir(estabelecimento_id=estabelecimento_id, data=ONTEM, itens=[item])
    sessao.add(anterior)
    await sessao.flush()

    antes = await sessao.scalar(select(func.count()).select_from(CardapioData))
    antes_vinculos = await sessao.scalar(
        select(func.count()).select_from(CardapioData.itens.property.secondary)
    )

    herdado = CardapioData.herdar_de(anterior, HOJE)

    depois = await sessao.scalar(select(func.count()).select_from(CardapioData))
    depois_vinculos = await sessao.scalar(
        select(func.count()).select_from(CardapioData.itens.property.secondary)
    )
    assert depois == antes
    assert depois_vinculos == antes_vinculos
    assert herdado not in sessao
    assert Decimal("20.00") == item.preco
