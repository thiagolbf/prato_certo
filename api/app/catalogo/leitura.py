"""Leitura do catálogo para outros módulos: objetos imutáveis, sem entidade (ADR-009).

`vendas` lê o catálogo só por aqui. Nunca recebe `ItemCardapio` nem `CardapioData`: o que
cruza a fronteira é o snapshot de leitura (RN-15, ADR-001).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.catalogo.modelos import Formato
from app.core.excecoes import RegraViolada


class TipoCardapio(StrEnum):
    PROPRIO = "PROPRIO"
    HERDADO = "HERDADO"
    VAZIO = "VAZIO"


@dataclass(frozen=True)
class ItemVendavel:
    item_id: int
    nome_prato: str
    nome_proteina: str
    formato: Formato
    preco: Decimal
    gramas_por_porcao: int


@dataclass(frozen=True)
class CardapioVigente:
    data: date
    tipo: TipoCardapio
    # Data do cardápio de onde o herdado veio; `None` para próprio e vazio (RN-09).
    data_origem: date | None
    itens: tuple[ItemVendavel, ...]


class ItemForaDoCardapio(RegraViolada):
    """O item não está no cardápio vigente da data (RN-19)."""
