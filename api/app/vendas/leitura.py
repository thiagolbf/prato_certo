"""Leitura de vendas para a API e outros módulos: objetos imutáveis, sem entidade (ADR-009)."""

from dataclasses import dataclass
from datetime import datetime
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
