"""Venda: snapshot, valor e proteína pela quantidade, limite de 1 a 20 e idempotência
(RN-14 a RN-20, ADR-004)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemVendavel
from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import RegraViolada
from app.core.valores import Dinheiro
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import gerar_hash
from app.vendas.excecoes import QuantidadeForaDoLimite
from app.vendas.modelos import Venda

AGORA = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)


def _marmita(**campos: object) -> ItemVendavel:
    base: dict[str, object] = {
        "item_id": 1,
        "nome_prato": "Frango grelhado",
        "nome_proteina": "Frango",
        "formato": Formato.MARMITA,
        "preco": Decimal("22.00"),
        "gramas_por_porcao": 150,
    }
    base.update(campos)
    return ItemVendavel(**base)  # type: ignore[arg-type]


def _registrar(item: ItemVendavel, quantidade: int = 3, chave: str = "chave-1") -> Venda:
    return Venda.registrar(
        estabelecimento_id=1,
        item=item,
        quantidade=quantidade,
        usuario_id=1,
        chave=chave,
        agora=AGORA,
    )


@pytest.mark.parametrize("quantidade", [0, 21, -1, True])
def test_quantidade_fora_de_1_a_20_e_recusada(quantidade: int) -> None:
    with pytest.raises(QuantidadeForaDoLimite):
        _registrar(_marmita(), quantidade=quantidade)


@pytest.mark.parametrize("chave", ["", "   "])
def test_chave_de_idempotencia_vazia_e_recusada(chave: str) -> None:
    with pytest.raises(RegraViolada):
        _registrar(_marmita(), chave=chave)


def test_valor_e_proteina_pela_quantidade() -> None:
    venda = _registrar(_marmita(), quantidade=3)

    assert venda.valor_total == Decimal("66.00")
    assert venda.proteina_total_g == 450


def test_registrar_copia_snapshot() -> None:
    item = _marmita()

    venda = _registrar(item)

    assert venda.prato_nome == "Frango grelhado"
    assert venda.proteina_nome == "Frango"
    assert venda.formato is Formato.MARMITA
    assert venda.preco_unitario == Decimal("22.00")
    assert venda.gramas_por_porcao == 150
    assert venda.item_cardapio_id == item.item_id
    assert venda.registrada_em == AGORA
    assert venda.registrada_por == 1
    assert venda.chave_idempotencia == "chave-1"
    assert venda.cancelada_em is None


async def test_chave_de_idempotencia_unica_por_estabelecimento(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = Usuario.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Joao",
        login="joao",
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=Perfil.OPERADOR,
    )
    sessao.add(usuario)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome="Frango")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Frango grelhado",
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    sessao.add(prato)
    await sessao.flush()
    item = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=Formato.MARMITA,
        preco=Dinheiro("22.00"),
    )
    sessao.add(item)
    await sessao.flush()
    vendavel = _marmita(item_id=item.id)

    sessao.add(
        Venda.registrar(
            estabelecimento_id=estabelecimento_id,
            item=vendavel,
            quantidade=1,
            usuario_id=usuario.id,
            chave="mesma-chave",
            agora=AGORA,
        )
    )
    await sessao.flush()
    sessao.add(
        Venda.registrar(
            estabelecimento_id=estabelecimento_id,
            item=vendavel,
            quantidade=2,
            usuario_id=usuario.id,
            chave="mesma-chave",
            agora=AGORA,
        )
    )

    with pytest.raises(IntegrityError):
        await sessao.flush()
