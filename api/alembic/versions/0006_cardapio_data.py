"""cardápio da data e associação com itens

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-08

Cardápio próprio por estabelecimento e data, único (RN-07), e a associação com os itens. Os
nomes das constraints seguem a convenção da `Base`, escritos com `op.f` para o alembic check.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cardapio_data",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("estabelecimento_id", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["estabelecimento_id"],
            ["estabelecimento.id"],
            name=op.f("fk_cardapio_data_estabelecimento_id_estabelecimento"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cardapio_data")),
        sa.UniqueConstraint(
            "estabelecimento_id", "data", name=op.f("uq_cardapio_data_estabelecimento_id_data")
        ),
    )
    op.create_table(
        "cardapio_item",
        sa.Column("cardapio_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cardapio_id"],
            ["cardapio_data.id"],
            name=op.f("fk_cardapio_item_cardapio_id_cardapio_data"),
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["item_cardapio.id"],
            name=op.f("fk_cardapio_item_item_id_item_cardapio"),
        ),
        sa.PrimaryKeyConstraint("cardapio_id", "item_id", name=op.f("pk_cardapio_item")),
    )


def downgrade() -> None:
    op.drop_table("cardapio_item")
    op.drop_table("cardapio_data")
