"""Leitura de vendas para a API e outros módulos: objetos imutáveis, sem entidade (ADR-009)."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.catalogo.modelos import Formato


@dataclass(frozen=True)
class VendaLeitura:
    id: int
    prato_nome: str
    proteina_nome: str
    formato: Formato
    quantidade: int
    preco_unitario: Decimal
    valor_total: Decimal
    proteina_total_g: int
    registrada_em: datetime
    cancelada_em: datetime | None


@dataclass(frozen=True)
class ResultadoRegistro:
    """`criada` é False quando a chave já existia: a venda devolvida é a original (RN-18)."""

    venda: VendaLeitura
    criada: bool


@dataclass(frozen=True)
class VendaAuditada:
    """Venda na lista do ADMIN, com autor e quem cancelou por nome (RN-51)."""

    id: int
    registrada_em: datetime
    prato_nome: str
    proteina_nome: str
    formato: Formato
    quantidade: int
    preco_unitario: Decimal
    valor_total: Decimal
    autor_nome: str
    cancelada_em: datetime | None
    cancelada_por_nome: str | None
    motivo_cancelamento: str | None


@dataclass(frozen=True)
class VendasDaData:
    """Lista de um dia com os totais, que excluem canceladas (RN-28)."""

    data: date
    vendas: tuple[VendaAuditada, ...]
    total_unidades: int
    total_valor: Decimal
