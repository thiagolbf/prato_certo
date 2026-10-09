"""Venda: registro append-only com snapshot do item no momento da venda (RN-14 a RN-20, ADR-004).

A venda não tem `UPDATE` de valor nem `DELETE`: copia o que vende no registro e, depois, só
pode ser cancelada logicamente. Entre módulos, entra só o `ItemVendavel` (ADR-001).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.catalogo.leitura import ItemVendavel
from app.catalogo.modelos import Formato
from app.core.excecoes import RegraViolada
from app.core.modelo_base import Base
from app.core.tempo import exigir_instante_com_fuso
from app.core.valores import Dinheiro, Gramagem
from app.vendas.excecoes import MotivoObrigatorio, QuantidadeForaDoLimite, VendaJaCancelada

QUANTIDADE_MINIMA = 1
QUANTIDADE_MAXIMA = 20


class Venda(Base):
    __tablename__ = "venda"
    __table_args__ = (
        CheckConstraint(
            f"quantidade BETWEEN {QUANTIDADE_MINIMA} AND {QUANTIDADE_MAXIMA}",
            name="quantidade_no_limite",
        ),
        # Segunda barreira do formato do snapshot, como em `item_cardapio` (a primeira é o enum).
        CheckConstraint("formato IN ('PF', 'MARMITA')", name="formato_valido"),
        # Idempotência: a mesma chave não cria segunda venda (RN-18). Nome explícito, como nos
        # índices do catálogo.
        Index(
            "uq_venda_estabelecimento_id_chave_idempotencia",
            "estabelecimento_id",
            "chave_idempotencia",
            unique=True,
        ),
        # Relatórios filtram por dia pelo intervalo UTC de `registrada_em` (RN-27, ADR-005).
        Index("ix_venda_estabelecimento_id_registrada_em", "estabelecimento_id", "registrada_em"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estabelecimento.id"))
    item_cardapio_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("item_cardapio.id"))
    quantidade: Mapped[int] = mapped_column(Integer)

    # Snapshot: copiado no registro e nunca mais alterado (RN-15, ADR-004).
    prato_nome: Mapped[str] = mapped_column(Text)
    proteina_nome: Mapped[str] = mapped_column(Text)
    formato: Mapped[Formato] = mapped_column(
        Enum(Formato, name="formato", native_enum=False, create_constraint=False, length=8)
    )
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    gramas_por_porcao: Mapped[int] = mapped_column(Integer)

    # Totais da venda (RN-16). Mais largo que o preço: preço máximo × 20 não cabe em 10,2.
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    proteina_total_g: Mapped[int] = mapped_column(Integer)

    registrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registrada_por: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.id"))
    chave_idempotencia: Mapped[str] = mapped_column(Text)

    # Cancelamento lógico: a linha fica, e os totais excluem as canceladas (ADR-004).
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_por: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuario.id"))
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text)

    @classmethod
    def registrar(
        cls,
        *,
        estabelecimento_id: int,
        item: ItemVendavel,
        quantidade: int,
        usuario_id: int,
        chave: str,
        agora: datetime,
    ) -> Venda:
        """Único caminho de criação: valida a quantidade, copia o snapshot e calcula os totais."""
        _exigir_quantidade(quantidade)
        _exigir_chave(chave)
        exigir_instante_com_fuso(agora)
        return cls(
            estabelecimento_id=estabelecimento_id,
            item_cardapio_id=item.item_id,
            quantidade=quantidade,
            prato_nome=item.nome_prato,
            proteina_nome=item.nome_proteina,
            formato=item.formato,
            preco_unitario=item.preco,
            gramas_por_porcao=item.gramas_por_porcao,
            valor_total=(Dinheiro(item.preco) * quantidade).valor,
            proteina_total_g=(Gramagem(item.gramas_por_porcao) * quantidade).gramas,
            registrada_em=agora,
            registrada_por=usuario_id,
            chave_idempotencia=chave,
        )

    def cancelar(self, *, por: int, motivo: str, agora: datetime) -> None:
        """A única mutação da venda: grava quando, quem e por quê, na linha inteira (RN-23, RN-24).

        Não olha a data da venda: qualquer data pode ser cancelada (RN-22). Não cancela de novo,
        para que o primeiro cancelamento fique intacto (RN-25, CA-17).
        """
        exigir_instante_com_fuso(agora)
        motivo_limpo = motivo.strip()
        if not motivo_limpo:
            raise MotivoObrigatorio("Informe o motivo do cancelamento (RN-26).")
        if self.cancelada_em is not None:
            raise VendaJaCancelada("Esta venda já foi cancelada.")
        self.cancelada_em = agora
        self.cancelada_por = por
        self.motivo_cancelamento = motivo_limpo


def _exigir_chave(chave: str) -> None:
    # Chave vazia colidiria com outra venda vazia e a segunda seria descartada como repetição.
    if not chave.strip():
        raise RegraViolada("A chave de idempotência é obrigatória (RN-18).")


def _exigir_quantidade(quantidade: int) -> None:
    # bool é subclasse de int, mas True não é uma quantidade.
    if (
        isinstance(quantidade, bool)
        or not isinstance(quantidade, int)
        or not QUANTIDADE_MINIMA <= quantidade <= QUANTIDADE_MAXIMA
    ):
        raise QuantidadeForaDoLimite(
            f"A quantidade de cada lançamento vai de {QUANTIDADE_MINIMA} a {QUANTIDADE_MAXIMA}."
        )
