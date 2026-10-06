"""estabelecimento

Revision ID: 0001
Revises:
Create Date: 2026-10-05 22:01:12.336748

Cria o dono de todo dado de domínio e semeia o único estabelecimento (ADR-003, RN-41).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    estabelecimento = op.create_table(
        "estabelecimento",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_estabelecimento")),
    )
    op.bulk_insert(estabelecimento, [{"nome": "Meu restaurante"}])


def downgrade() -> None:
    op.drop_table("estabelecimento")
