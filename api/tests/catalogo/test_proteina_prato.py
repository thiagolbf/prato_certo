"""Proteína e prato: nome único sem maiúsculas nem espaços, gramagem positiva (RN-01, RN-02, RN-59).

Os testes de banco usam a sessão de teste (transação desfeita) e `begin_nested` quando a
violação de unicidade precisa ser provocada. O relacionamento é `lazy="raise"` (ADR-009).
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import Prato, Proteina
from app.core.estabelecimento import Estabelecimento, estabelecimento_atual
from app.core.excecoes import RegraViolada


async def _proteina(
    sessao: AsyncSession, nome: str, estabelecimento_id: int | None = None
) -> Proteina:
    proteina = Proteina.criar(
        estabelecimento_id=estabelecimento_id or await estabelecimento_atual(sessao), nome=nome
    )
    sessao.add(proteina)
    await sessao.flush()
    return proteina


def _prato(proteina: Proteina, nome: str = "PF de frango", gramas: int = 120) -> Prato:
    return Prato.criar(
        estabelecimento_id=proteina.estabelecimento_id,
        nome=nome,
        proteina_id=proteina.id,
        gramas_por_porcao=gramas,
    )


async def test_nome_de_proteina_unico_sem_maiusculas_nem_espacos(sessao: AsyncSession) -> None:
    await _proteina(sessao, "Frango")

    with pytest.raises(IntegrityError):
        async with sessao.begin_nested():
            await _proteina(sessao, " frango ")


async def test_nome_de_prato_unico_sem_maiusculas_nem_espacos(sessao: AsyncSession) -> None:
    proteina = await _proteina(sessao, "Carne")
    sessao.add(_prato(proteina, nome="PF Bife"))
    await sessao.flush()

    with pytest.raises(IntegrityError):
        async with sessao.begin_nested():
            sessao.add(_prato(proteina, nome=" pf bife "))
            await sessao.flush()


async def test_mesmo_nome_em_outro_estabelecimento_e_aceito(sessao: AsyncSession) -> None:
    await _proteina(sessao, "Frango")
    outro = Estabelecimento(nome="Outro restaurante")
    sessao.add(outro)
    await sessao.flush()

    await _proteina(sessao, "Frango", estabelecimento_id=outro.id)

    contagem = (
        await sessao.scalars(select(Proteina).where(Proteina.estabelecimento_id == outro.id))
    ).all()
    assert len(contagem) == 1


def test_gramagem_precisa_ser_positiva() -> None:
    with pytest.raises(ValueError):
        Prato.criar(estabelecimento_id=1, nome="PF", proteina_id=1, gramas_por_porcao=0)
    with pytest.raises(ValueError):
        Prato.criar(estabelecimento_id=1, nome="PF", proteina_id=1, gramas_por_porcao=-5)


def test_desativar_e_reativar_prato() -> None:
    prato = Prato.criar(estabelecimento_id=1, nome="PF", proteina_id=1, gramas_por_porcao=120)
    assert prato.ativo is True

    prato.desativar()
    assert prato.ativo is False

    prato.reativar()
    assert prato.ativo is True


async def test_relacionamento_nao_carregado_falha_cedo(sessao: AsyncSession) -> None:
    proteina = await _proteina(sessao, "Ovo")
    prato = _prato(proteina, nome="PF de ovo")
    sessao.add(prato)
    await sessao.flush()
    sessao.expunge_all()

    carregado = (await sessao.scalars(select(Prato).where(Prato.nome == "PF de ovo"))).one()

    with pytest.raises(InvalidRequestError, match="lazy"):
        _ = carregado.proteina


def test_nome_em_branco_e_recusado() -> None:
    with pytest.raises(RegraViolada):
        Proteina.criar(estabelecimento_id=1, nome="   ")
    with pytest.raises(RegraViolada):
        Prato.criar(estabelecimento_id=1, nome="", proteina_id=1, gramas_por_porcao=120)
