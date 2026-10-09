"""Formas dos resultados agregados do fechamento (RN-29, RN-30).

São objetos de leitura imutáveis, não entidades nem contrato HTTP: as consultas do módulo
devolvem essas linhas, e a rota (T-33) as traduz para o schema de resposta.
"""

from dataclasses import dataclass

from app.catalogo.modelos import Formato


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
