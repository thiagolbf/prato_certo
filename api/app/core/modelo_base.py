"""Base declarativa dos modelos SQLAlchemy, com a convenção de nomes do banco (T-03).

Constraints e índices ganham nomes previsíveis, para as migrations conseguirem
referenciá-los e desfazê-los. Tabelas: singular, snake_case, em português.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

CONVENCAO_DE_NOMES = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_DE_NOMES)
