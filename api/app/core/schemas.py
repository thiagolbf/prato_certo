"""Base de todo schema de entrada da API (RN-46, ADR-009).

Schemas Pydantic são contrato HTTP, separados dos modelos SQLAlchemy. Todo schema que
recebe dado do cliente herda de `ModeloEstrito`; os limites de cada campo (nome até 60,
motivo até 200, senha com mínimo de 8...) ficam nos schemas de cada módulo.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Texto que chega exatamente como digitado, sem o corte de espaços do `ModeloEstrito`.
# Toda senha usa este tipo: o hash é do que o usuário digitou, e o mínimo de 8 da RN-60
# conta os mesmos caracteres que a tela (REVIEW-T-07, R-01).
TextoLiteral = Annotated[str, StringConstraints(strip_whitespace=False)]


class ModeloEstrito(BaseModel):
    """Campo desconhecido é recusado (422), não ignorado; texto chega sem espaços nas pontas.

    Exceção: campo declarado como `TextoLiteral` (senha) não tem os espaços cortados.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
