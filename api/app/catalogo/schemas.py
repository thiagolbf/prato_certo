"""Contrato HTTP do catálogo (ADR-009): schemas de entrada e de resposta.

Entrada herda de `ModeloEstrito`, que corta espaços nas pontas: "  Frango " vira "Frango".
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.catalogo.leitura import TipoCardapio
from app.catalogo.modelos import Formato
from app.core.schemas import ModeloEstrito

# Limite de nome da SPEC-UI (lacuna 16), igual ao de usuários.
Nome = Annotated[str, Field(min_length=1, max_length=60)]


class NovaProteina(ModeloEstrito):
    nome: Nome


class RenomearProteina(ModeloEstrito):
    nome: Nome


class ProteinaListada(BaseModel):
    id: int
    nome: str
    ativo: bool
    pratos_ativos: int


class NovoPrato(ModeloEstrito):
    nome: Nome
    proteina_id: int
    gramas_por_porcao: Annotated[int, Field(gt=0, le=10000)]


class RenomearPrato(ModeloEstrito):
    nome: Nome


class AlterarGramagem(ModeloEstrito):
    gramas_por_porcao: Annotated[int, Field(gt=0, le=10000)]


class PratoListado(BaseModel):
    id: int
    nome: str
    proteina_id: int
    proteina_nome: str
    gramas_por_porcao: int
    ativo: bool
    itens_ativos: int


# Preço: Decimal com no máximo duas casas e positivo (RN-03, ADR-009). Nunca float.
Preco = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]


class NovoItem(ModeloEstrito):
    prato_id: int
    formato: Formato
    preco: Preco


class AlterarPreco(ModeloEstrito):
    # Só o preço: prato e formato não aparecem aqui, e campo extra é recusado (422).
    preco: Preco


class ItemListado(BaseModel):
    id: int
    prato_id: int
    prato_nome: str
    nome: str
    formato: Formato
    gramas_por_porcao: int
    preco: Decimal
    ativo: bool


class ItemVigenteListado(BaseModel):
    """Item do cardápio que o Operador pode tocar: com o preço que aparece na tela (RN-40)."""

    item_id: int
    nome_prato: str
    nome_proteina: str
    formato: Formato
    gramas_por_porcao: int
    preco: Decimal


class CardapioListado(BaseModel):
    data: date
    tipo: TipoCardapio
    # Data do cardápio de onde o herdado veio; `None` para próprio e vazio (RN-09).
    data_origem: date | None
    itens: list[ItemVigenteListado]


class CardapioDaDataListado(CardapioListado):
    # Data passada: o cardápio é só de leitura (RN-50).
    passada: bool


class DefinirCardapio(ModeloEstrito):
    # Lista vazia chega até a entidade, que a recusa (RN-57): a regra fica num lugar só.
    itens: list[int]
