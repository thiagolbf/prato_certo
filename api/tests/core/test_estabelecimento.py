"""Estabelecimento único semeado e a dependência que entrega o seu id (ADR-003, RN-41)."""

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.estabelecimento import Estabelecimento, estabelecimento_atual


async def test_estabelecimento_atual_devolve_o_id_do_estabelecimento_semeado(
    sessao: AsyncSession,
) -> None:
    id_semeado = await sessao.scalar(select(Estabelecimento.id))

    assert await estabelecimento_atual(sessao) == id_semeado


async def test_estabelecimento_atual_falha_sem_estabelecimento(sessao: AsyncSession) -> None:
    await sessao.execute(delete(Estabelecimento))

    with pytest.raises(RuntimeError, match="estabelecimento"):
        await estabelecimento_atual(sessao)


async def test_estabelecimento_atual_falha_com_mais_de_um(sessao: AsyncSession) -> None:
    """Até a T-10 só existe um; escolher um entre vários vazaria dado de outro (RN-41)."""
    await sessao.execute(insert(Estabelecimento).values(nome="Outro restaurante"))

    with pytest.raises(RuntimeError, match="estabelecimento"):
        await estabelecimento_atual(sessao)
