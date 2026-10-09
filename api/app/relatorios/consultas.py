"""Consultas agregadas do fechamento do dia (RN-27 a RN-30; ADR-004, ADR-005, ADR-007).

Procedural, sem entidade e sem service (ADR-009). Cada função recebe a sessão, o
`estabelecimento_id` e o intervalo UTC `[inicio, fim)` do dia operacional (ADR-005), e devolve
linhas agregadas pelo banco. Nenhuma soma é feita em Python sobre linhas de venda. Toda
consulta exclui as canceladas (RN-28).
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.relatorios.schemas import ProteinaConsumida, UnidadesPorItem, UnidadesPorPrato
from app.vendas.modelos import Venda


def _nao_canceladas_no_periodo(estabelecimento_id: int, inicio: datetime, fim: datetime) -> tuple:
    return (
        Venda.estabelecimento_id == estabelecimento_id,
        Venda.registrada_em >= inicio,
        Venda.registrada_em < fim,
        Venda.cancelada_em.is_(None),
    )


async def unidades_por_item(
    sessao: AsyncSession, estabelecimento_id: int, inicio: datetime, fim: datetime
) -> list[UnidadesPorItem]:
    """Unidades por item do cardápio, PF e marmita em linhas separadas (RN-29)."""
    unidades = func.sum(Venda.quantidade).label("unidades")
    linhas = await sessao.execute(
        select(Venda.item_cardapio_id, Venda.prato_nome, Venda.formato, unidades)
        .where(*_nao_canceladas_no_periodo(estabelecimento_id, inicio, fim))
        .group_by(Venda.item_cardapio_id, Venda.prato_nome, Venda.formato)
        .order_by(Venda.prato_nome, Venda.formato)
    )
    return [
        UnidadesPorItem(
            item_id=linha.item_cardapio_id,
            prato_nome=linha.prato_nome,
            formato=linha.formato,
            unidades=int(linha.unidades),
        )
        for linha in linhas
    ]


async def unidades_por_prato(
    sessao: AsyncSession, estabelecimento_id: int, inicio: datetime, fim: datetime
) -> list[UnidadesPorPrato]:
    """Unidades por prato, somando PF e marmita (RN-29)."""
    unidades = func.sum(Venda.quantidade).label("unidades")
    linhas = await sessao.execute(
        select(Venda.prato_nome, unidades)
        .where(*_nao_canceladas_no_periodo(estabelecimento_id, inicio, fim))
        .group_by(Venda.prato_nome)
        .order_by(Venda.prato_nome)
    )
    return [
        UnidadesPorPrato(prato_nome=linha.prato_nome, unidades=int(linha.unidades))
        for linha in linhas
    ]


async def total_unidades(
    sessao: AsyncSession, estabelecimento_id: int, inicio: datetime, fim: datetime
) -> int:
    """Total de unidades do período, sem as canceladas (RN-29)."""
    total = await sessao.scalar(
        select(func.coalesce(func.sum(Venda.quantidade), 0)).where(
            *_nao_canceladas_no_periodo(estabelecimento_id, inicio, fim)
        )
    )
    return int(total)


async def proteina_por_tipo(
    sessao: AsyncSession, estabelecimento_id: int, inicio: datetime, fim: datetime
) -> list[ProteinaConsumida]:
    """Gramas consumidas por proteína: gramagem do snapshot × quantidade (RN-30)."""
    gramas = func.sum(Venda.gramas_por_porcao * Venda.quantidade).label("gramas")
    linhas = await sessao.execute(
        select(Venda.proteina_nome, gramas)
        .where(*_nao_canceladas_no_periodo(estabelecimento_id, inicio, fim))
        .group_by(Venda.proteina_nome)
        .order_by(Venda.proteina_nome)
    )
    return [
        ProteinaConsumida(proteina_nome=linha.proteina_nome, gramas=int(linha.gramas))
        for linha in linhas
    ]
