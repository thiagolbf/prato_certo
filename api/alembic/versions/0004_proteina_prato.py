"""proteina e prato

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08

Proteína e prato com nome único por estabelecimento, sem diferenciar maiúsculas nem espaços
(RN-01, RN-59), e gramagem positiva por prato (RN-02). O índice por expressão foi escrito à
mão: o autogenerate não o detecta.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proteina",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("estabelecimento_id", sa.BigInteger(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["estabelecimento_id"],
            ["estabelecimento.id"],
            name=op.f("fk_proteina_estabelecimento_id_estabelecimento"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proteina")),
    )
    op.create_index(
        "uq_proteina_estabelecimento_id_nome",
        "proteina",
        ["estabelecimento_id", sa.literal_column("lower(trim(nome))")],
        unique=True,
    )
    op.create_table(
        "prato",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("estabelecimento_id", sa.BigInteger(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("proteina_id", sa.BigInteger(), nullable=False),
        sa.Column("gramas_por_porcao", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "gramas_por_porcao > 0", name=op.f("ck_prato_gramas_por_porcao_positiva")
        ),
        sa.ForeignKeyConstraint(
            ["estabelecimento_id"],
            ["estabelecimento.id"],
            name=op.f("fk_prato_estabelecimento_id_estabelecimento"),
        ),
        sa.ForeignKeyConstraint(
            ["proteina_id"], ["proteina.id"], name=op.f("fk_prato_proteina_id_proteina")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prato")),
    )
    op.create_index(
        "uq_prato_estabelecimento_id_nome",
        "prato",
        ["estabelecimento_id", sa.literal_column("lower(trim(nome))")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_prato_estabelecimento_id_nome", table_name="prato")
    op.drop_table("prato")
    op.drop_index("uq_proteina_estabelecimento_id_nome", table_name="proteina")
    op.drop_table("proteina")
