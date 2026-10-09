"""Entidades do catálogo: Proteina e Prato (RN-01, RN-02, RN-59, ADR-009).

Nome único por estabelecimento, sem diferenciar maiúsculas nem espaços nas pontas: o índice
é por expressão, `lower(trim(nome))`. A gramagem é conferida pelo `Gramagem` do core.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.excecoes import RegraViolada
from app.core.modelo_base import Base
from app.core.valores import Dinheiro, Gramagem


def _nome_valido(nome: str) -> str:
    """Nome em branco não identifica nada (RN-01, RN-59): recusado pela entidade."""
    if not nome.strip():
        raise RegraViolada("O nome não pode ficar em branco.")
    return nome.strip()


class Proteina(Base):
    __tablename__ = "proteina"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estabelecimento.id"))
    nome: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean)

    @classmethod
    def criar(cls, *, estabelecimento_id: int, nome: str) -> Proteina:
        return cls(estabelecimento_id=estabelecimento_id, nome=_nome_valido(nome), ativo=True)

    def renomear(self, nome: str) -> None:
        self.nome = _nome_valido(nome)

    def desativar(self) -> None:
        """Proteínas nunca são apagadas, só desativadas (RN-01)."""
        self.ativo = False

    def reativar(self) -> None:
        self.ativo = True


class Prato(Base):
    __tablename__ = "prato"
    __table_args__ = (CheckConstraint("gramas_por_porcao > 0", name="gramas_por_porcao_positiva"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estabelecimento.id"))
    nome: Mapped[str] = mapped_column(Text)
    proteina_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("proteina.id"))
    gramas_por_porcao: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean)
    # `lazy="raise"`: quem usa a proteína carrega explicitamente (selectinload/joinedload).
    proteina: Mapped[Proteina] = relationship(lazy="raise")

    @classmethod
    def criar(
        cls, *, estabelecimento_id: int, nome: str, proteina_id: int, gramas_por_porcao: int
    ) -> Prato:
        Gramagem(gramas_por_porcao)  # recusa zero, negativo e não inteiro
        return cls(
            estabelecimento_id=estabelecimento_id,
            nome=_nome_valido(nome),
            proteina_id=proteina_id,
            gramas_por_porcao=gramas_por_porcao,
            ativo=True,
        )

    def alterar_gramagem(self, gramas: int) -> None:
        self.gramas_por_porcao = Gramagem(gramas).gramas

    def desativar(self) -> None:
        self.ativo = False

    def reativar(self) -> None:
        self.ativo = True


class Formato(StrEnum):
    PF = "PF"
    MARMITA = "MARMITA"


class ItemCardapio(Base):
    """Par prato × formato, com preço próprio (RN-03). É o item que o Operador toca na tela."""

    __tablename__ = "item_cardapio"
    __table_args__ = (
        CheckConstraint("preco > 0", name="preco_positivo"),
        CheckConstraint("formato IN ('PF', 'MARMITA')", name="formato_valido"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estabelecimento.id"))
    prato_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("prato.id"))
    formato: Mapped[Formato] = mapped_column(
        Enum(Formato, name="formato", native_enum=False, create_constraint=False, length=8)
    )
    # Numeric, nunca float (ADR-009): o Dinheiro entra e sai como Decimal.
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ativo: Mapped[bool] = mapped_column(Boolean)

    @classmethod
    def criar(
        cls, *, estabelecimento_id: int, prato_id: int, formato: Formato, preco: Dinheiro
    ) -> ItemCardapio:
        _exigir_preco_positivo(preco)
        return cls(
            estabelecimento_id=estabelecimento_id,
            prato_id=prato_id,
            formato=formato,
            preco=preco.valor,
            ativo=True,
        )

    def alterar_preco(self, preco: Dinheiro) -> None:
        _exigir_preco_positivo(preco)
        self.preco = preco.valor

    def desativar(self) -> None:
        self.ativo = False

    def reativar(self) -> None:
        self.ativo = True


def _exigir_preco_positivo(preco: Dinheiro) -> None:
    if preco <= Dinheiro.zero():
        raise ValueError(f"preço precisa ser positivo, recebido {preco}")


# Nome único por estabelecimento, sem maiúsculas nem espaços nas pontas (RN-59). Índice por
# expressão: fica depois da classe porque referencia a coluna.
Index(
    "uq_proteina_estabelecimento_id_nome",
    Proteina.estabelecimento_id,
    text("lower(TRIM(BOTH FROM nome))"),
    unique=True,
)
Index(
    "uq_prato_estabelecimento_id_nome",
    Prato.estabelecimento_id,
    text("lower(TRIM(BOTH FROM nome))"),
    unique=True,
)

# Um item por prato e formato, desativado ou não (RN-59).
Index(
    "uq_item_cardapio_prato_id_formato",
    ItemCardapio.prato_id,
    ItemCardapio.formato,
    unique=True,
)
