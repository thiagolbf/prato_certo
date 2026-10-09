"""Registro idempotente de venda (RN-17, RN-18, RN-19; ADR-004, ADR-005).

O relógio é injetado: o instante do servidor é o que o teste manda. O teste de envios
simultâneos grava dados de verdade, em duas sessões, e limpa tudo no fim.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemForaDoCardapio
from app.catalogo.modelos import (
    CardapioData,
    Formato,
    ItemCardapio,
    Prato,
    Proteina,
    cardapio_item,
)
from app.catalogo.repositorio import RepositorioCardapios
from app.catalogo.servico_cardapio import ServicoCardapio
from app.core.db import criar_fabrica_sessoes
from app.core.estabelecimento import estabelecimento_atual
from app.core.tempo import DiaOperacional
from app.core.valores import Dinheiro
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import gerar_hash
from app.vendas.modelos import Venda
from app.vendas.repositorio import RepositorioVendas
from app.vendas.servico import ServicoVendas

# 12:00 UTC é 09:00 em São Paulo: o dia operacional é 08/10.
INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
HOJE = date(2026, 10, 8)


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante


async def _usuario(sessao: AsyncSession, login: str = "joao") -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=Perfil.OPERADOR,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _item(sessao: AsyncSession, nome_prato: str) -> ItemCardapio:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Frango {nome_prato}")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome=nome_prato,
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    sessao.add(prato)
    await sessao.flush()
    item = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=Formato.MARMITA,
        preco=Dinheiro("22.00"),
    )
    sessao.add(item)
    await sessao.flush()
    return item


async def _cardapio_de_hoje(sessao: AsyncSession, *itens: ItemCardapio) -> None:
    sessao.add(
        CardapioData.definir(
            estabelecimento_id=await estabelecimento_atual(sessao),
            data=HOJE,
            itens=list(itens),
            hoje=HOJE,
        )
    )
    await sessao.flush()


def _servico(sessao: AsyncSession, estabelecimento_id: int, relogio: RelogioFixo) -> ServicoVendas:
    return ServicoVendas(
        RepositorioVendas(sessao, estabelecimento_id),
        ServicoCardapio(RepositorioCardapios(sessao, estabelecimento_id)),
        relogio,
    )


async def _vendas_com_chave(sessao: AsyncSession, chave: str) -> int:
    return await sessao.scalar(
        select(func.count()).select_from(Venda).where(Venda.chave_idempotencia == chave)
    )


async def test_CA_03_reenvio_da_mesma_chave_nao_duplica(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    servico = _servico(sessao, estabelecimento_id, RelogioFixo(INICIO))

    primeira = await servico.registrar(item.id, 2, "chave-a", usuario.id)
    reenvio = await servico.registrar(item.id, 5, "chave-a", usuario.id)

    assert primeira.criada is True
    assert reenvio.criada is False
    assert reenvio.venda.id == primeira.venda.id
    # O reenvio traz outra quantidade, e mesmo assim a original é a que vale.
    assert reenvio.venda.quantidade == 2
    assert await _vendas_com_chave(sessao, "chave-a") == 1


async def test_CA_03_envios_simultaneos_da_mesma_chave_criam_uma_venda(engine) -> None:
    """Duas requisições em paralelo com a mesma chave: uma cria, a outra devolve a original."""
    fabrica = criar_fabrica_sessoes(engine)
    sufixo = uuid.uuid4().hex[:8]
    chave = f"chave-{sufixo}"
    login = f"op{sufixo}"
    async with fabrica() as sessao, sessao.begin():
        estabelecimento_id = await estabelecimento_atual(sessao)
        usuario = await _usuario(sessao, login)
        item = await _item(sessao, f"Prato {sufixo}")
        await _cardapio_de_hoje(sessao, item)
        usuario_id, item_id = usuario.id, item.id

    async def registrar() -> bool:
        async with fabrica() as sessao, sessao.begin():
            servico = _servico(sessao, estabelecimento_id, RelogioFixo(INICIO))
            return (await servico.registrar(item_id, 1, chave, usuario_id)).criada

    try:
        criadas = await asyncio.gather(registrar(), registrar())

        assert sorted(criadas) == [False, True]
        async with fabrica() as sessao:
            assert await _vendas_com_chave(sessao, chave) == 1
    finally:
        async with fabrica() as sessao, sessao.begin():
            await sessao.execute(delete(Venda).where(Venda.chave_idempotencia == chave))
            await sessao.execute(
                delete(cardapio_item).where(
                    cardapio_item.c.item_id == item_id,
                )
            )
            await sessao.execute(delete(CardapioData).where(CardapioData.data == HOJE))
            await sessao.execute(delete(ItemCardapio).where(ItemCardapio.id == item_id))
            await sessao.execute(delete(Prato).where(Prato.nome == f"Prato {sufixo}"))
            await sessao.execute(delete(Proteina).where(Proteina.nome == f"Frango Prato {sufixo}"))
            await sessao.execute(delete(Usuario).where(Usuario.login == login))


async def test_CA_06_item_fora_do_cardapio_e_recusado(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    no_cardapio = await _item(sessao, "Feijoada")
    fora = await _item(sessao, "Strogonoff")
    await _cardapio_de_hoje(sessao, no_cardapio)
    servico = _servico(sessao, estabelecimento_id, RelogioFixo(INICIO))

    with pytest.raises(ItemForaDoCardapio):
        await servico.registrar(fora.id, 1, "chave-fora", usuario.id)

    assert await _vendas_com_chave(sessao, "chave-fora") == 0


async def test_CA_28_instante_vem_do_servidor(sessao: AsyncSession) -> None:
    """O instante e o dia são do relógio do servidor. Nada que o cliente envie os altera."""
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    item = await _item(sessao, "Feijoada")
    await _cardapio_de_hoje(sessao, item)
    servico = _servico(sessao, estabelecimento_id, RelogioFixo(INICIO))

    resultado = await servico.registrar(item.id, 1, "chave-relogio", usuario.id)

    venda = await sessao.get(Venda, resultado.venda.id)
    assert venda.registrada_em == INICIO
    assert DiaOperacional.do_instante(venda.registrada_em).data == HOJE
