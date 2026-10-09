"""Formas dos resultados agregados do fechamento (RN-29, RN-30).

São objetos de leitura imutáveis, não entidades nem contrato HTTP: as consultas do módulo
devolvem essas linhas, e a rota (T-33) as traduz para o schema de resposta.
"""

from dataclasses import dataclass
from datetime import datetime

from app.catalogo.modelos import Formato
from app.core.valores import Dinheiro


@dataclass(frozen=True)
class UnidadesPorItem:
    """Unidades de um item do cardápio, com PF e marmita separados (RN-29)."""

    item_id: int
    prato_nome: str
    formato: Formato
    unidades: int


@dataclass(frozen=True)
class UnidadesPorPrato:
    """Unidades de um prato, somando os formatos (RN-29)."""

    prato_nome: str
    unidades: int


@dataclass(frozen=True)
class ProteinaConsumida:
    """Gramas consumidas de uma proteína: gramagem do snapshot × quantidade (RN-30)."""

    proteina_nome: str
    gramas: int


@dataclass(frozen=True)
class FaturamentoPorFormato:
    """Faturamento de um formato, sem as canceladas (RN-31)."""

    formato: Formato
    valor: Dinheiro


@dataclass(frozen=True)
class CancelamentoPosterior:
    """Venda de um dia cancelada depois dele: quem cancelou, quando e por quê (RN-61).

    Traz o id de quem cancelou; o nome é resolvido pela rota, no serviço de identidade (ADR-001).
    """

    venda_id: int
    prato_nome: str
    quantidade: int
    valor_total: Dinheiro
    cancelada_em: datetime
    cancelada_por_id: int
    motivo_cancelamento: str
