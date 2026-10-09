"""Estabelecimento: o dono de todo dado de domínio (ADR-003, RN-41).

Convenção que toda tarefa seguinte cumpre: toda tabela de domínio tem `estabelecimento_id`,
e todo repositório recebe o `estabelecimento_id` no construtor e filtra toda consulta por ele.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import SessaoDaRequisicao
from app.core.modelo_base import Base


class Estabelecimento(Base):
    __tablename__ = "estabelecimento"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nome: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def estabelecimento_atual(
    sessao: SessaoDaRequisicao,
) -> int:
    """Id do único estabelecimento; a partir da T-10, passa a vir do usuário autenticado."""
    ids = (await sessao.scalars(select(Estabelecimento.id).limit(2))).all()
    if len(ids) != 1:
        raise RuntimeError(
            f"Esperado exatamente um estabelecimento cadastrado, encontrados {len(ids)}"
        )
    return ids[0]
