"""item de cardápio

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-08

Item prato × formato com preço próprio em Numeric(10, 2) (RN-03, RN-59). Um item por prato e
formato, desativado ou não. CHECKs de preço positivo e de formato escritos à mão, no padrão
da 0002: o Enum não cria a constraint.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_cardapio",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("estabelecimento_id", sa.BigInteger(), nullable=False),
        sa.Column("prato_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "formato",
            sa.Enum(
                "PF",
                "MARMITA",
                name="formato",
                native_enum=False,
                create_constraint=False,
                length=8,
            ),
            nullable=False,
        ),
        sa.Column("preco", sa.Numeric(10, 2), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.CheckConstraint("preco > 0", name=op.f("ck_item_cardapio_preco_positivo")),
        sa.CheckConstraint(
            "formato IN ('PF', 'MARMITA')", name=op.f("ck_item_cardapio_formato_valido")
        ),
        sa.ForeignKeyConstraint(
            ["estabelecimento_id"],
            ["estabelecimento.id"],
            name=op.f("fk_item_cardapio_estabelecimento_id_estabelecimento"),
        ),
        sa.ForeignKeyConstraint(
            ["prato_id"], ["prato.id"], name=op.f("fk_item_cardapio_prato_id_prato")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_cardapio")),
    )
    op.create_index(
        "uq_item_cardapio_prato_id_formato",
        "item_cardapio",
        ["prato_id", "formato"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_item_cardapio_prato_id_formato", table_name="item_cardapio")
    op.drop_table("item_cardapio")
