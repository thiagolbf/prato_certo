"""Contrato HTTP de vendas (ADR-009): o pedido de registro e a venda devolvida.

O teto de quantidade não está aqui: é regra de domínio (RN-14), e a recusa volta como 422 com
a mensagem de negócio, que a UI mostra no estado `.recusado`.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.catalogo.modelos import Formato
from app.core.schemas import ModeloEstrito

# A chave vem do clique no aparelho (ADR-004); o limite é folga sobre um UUID.
ChaveIdempotencia = Annotated[str, Field(min_length=1, max_length=64)]


class NovaVenda(ModeloEstrito):
    item_id: int
    quantidade: int
    chave_idempotencia: ChaveIdempotencia


class VendaDoDia(BaseModel):
    """Venda na lista do próprio Operador. Não tem campo de preço nem de valor: a restrição é
    deste contrato HTTP (RN-40), não da entidade."""

    id: int
    horario: datetime
    prato_nome: str
    proteina_nome: str
    formato: Formato
    quantidade: int
    cancelada: bool


class CancelarVenda(ModeloEstrito):
    # Motivo vazio é recusado pela entidade (RN-26), com a mensagem de negócio.
    motivo: Annotated[str, Field(max_length=200)]


class VendaRegistrada(BaseModel):
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
