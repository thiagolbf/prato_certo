"""Contrato HTTP do fechamento do dia (ADR-009, RN-29 a RN-31, RN-61).

Só o formato da resposta. As formas de leitura das consultas ficam em `leitura.py`. Valores
monetários saem como texto decimal, nunca como float (`CLAUDE.md`).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.catalogo.modelos import Formato


class UnidadesPorItemListado(BaseModel):
    item_id: int
    prato_nome: str
    formato: Formato
    unidades: int


class UnidadesPorPratoListado(BaseModel):
    prato_nome: str
    unidades: int


class ProteinaListada(BaseModel):
    proteina_nome: str
    gramas: int


class FaturamentoPorFormatoListado(BaseModel):
    formato: Formato
    valor: Decimal


class CancelamentoPosteriorListado(BaseModel):
    venda_id: int
    prato_nome: str
    quantidade: int
    valor_total: Decimal
    cancelada_em: datetime
    cancelada_por: str
    motivo_cancelamento: str


class QuebraDiaListada(BaseModel):
    dia: date
    unidades: int
    faturamento: Decimal


class FechamentoMesListado(BaseModel):
    mes: str
    # Verdadeiro quando o mês é o corrente: os números ainda estão mudando.
    parcial: bool
    total_unidades: int
    unidades_por_item: list[UnidadesPorItemListado]
    unidades_por_prato: list[UnidadesPorPratoListado]
    proteina_por_tipo: list[ProteinaListada]
    faturamento_por_formato: list[FaturamentoPorFormatoListado]
    faturamento_total: Decimal
    quebra_por_dia: list[QuebraDiaListada]


class FechamentoDiaListado(BaseModel):
    data: date
    # Verdadeiro quando a data é o dia operacional corrente: os números ainda estão mudando.
    parcial: bool
    total_unidades: int
    unidades_por_item: list[UnidadesPorItemListado]
    unidades_por_prato: list[UnidadesPorPratoListado]
    proteina_por_tipo: list[ProteinaListada]
    faturamento_por_formato: list[FaturamentoPorFormatoListado]
    faturamento_total: Decimal
    cancelamentos_posteriores: list[CancelamentoPosteriorListado]
