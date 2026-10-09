"""Item de cardápio: prato × formato, com preço próprio (RN-03, RN-59).

O par prato × formato é único, desativado ou não. O preço é `Dinheiro` na entrada e `Decimal`
no banco (ADR-009). Os testes de banco usam a sessão de teste e `begin_nested` quando a
violação de unicidade precisa acontecer.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.valores import Dinheiro


async def _prato(sessao: AsyncSession, nome: str = "PF de frango") -> Prato:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Frango {nome}")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome=nome,
        proteina_id=proteina.id,
        gramas_por_porcao=120,
    )
    sessao.add(prato)
    await sessao.flush()
    return prato


def _item(prato: Prato, formato: Formato, preco: str = "12.50") -> ItemCardapio:
    return ItemCardapio.criar(
        estabelecimento_id=prato.estabelecimento_id,
        prato_id=prato.id,
        formato=formato,
        preco=Dinheiro(preco),
    )


def test_preco_precisa_ser_positivo() -> None:
    for valor in ("0", "-1.00"):
        with pytest.raises(ValueError):
            ItemCardapio.criar(
                estabelecimento_id=1, prato_id=1, formato=Formato.PF, preco=Dinheiro(valor)
            )


def test_alterar_preco() -> None:
    item = ItemCardapio.criar(
        estabelecimento_id=1, prato_id=1, formato=Formato.PF, preco=Dinheiro("12.50")
    )

    item.alterar_preco(Dinheiro("14.00"))
    assert item.preco == Decimal("14.00")

    with pytest.raises(ValueError):
        item.alterar_preco(Dinheiro("0"))
    assert item.preco == Decimal("14.00")


async def test_item_unico_por_prato_e_formato(sessao: AsyncSession) -> None:
    prato = await _prato(sessao)
    pf = _item(prato, Formato.PF)
    sessao.add(pf)
    await sessao.flush()

    # Desativado continua contando: o par não pode se repetir (RN-59).
    pf.desativar()
    await sessao.flush()

    with pytest.raises(IntegrityError):
        async with sessao.begin_nested():
            sessao.add(_item(prato, Formato.PF, preco="13.00"))
            await sessao.flush()

    sessao.add(_item(prato, Formato.MARMITA))
    await sessao.flush()  # o outro formato é aceito


async def test_preco_persistido_como_decimal(sessao: AsyncSession) -> None:
    prato = await _prato(sessao, nome="Marmita de carne")
    sessao.add(_item(prato, Formato.MARMITA, preco="12.50"))
    await sessao.flush()
    sessao.expunge_all()

    lido = (
        await sessao.scalars(select(ItemCardapio).where(ItemCardapio.prato_id == prato.id))
    ).one()

    assert isinstance(lido.preco, Decimal)
    assert lido.preco == Decimal("12.50")
