"""Contrato HTTP do catálogo (ADR-009): schemas de entrada e de resposta.

Entrada herda de `ModeloEstrito`, que corta espaços nas pontas: "  Frango " vira "Frango".
"""

from typing import Annotated

from pydantic import BaseModel, Field

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
