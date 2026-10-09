"""Cancelamento lógico da venda (RN-22 a RN-26; ADR-004, ADR-009).

Os unitários provam a entidade sem banco. Os de integração gravam de verdade e confirmam que a
linha continua no banco depois do cancelamento.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemVendavel
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
from app.core.excecoes import NaoEncontrado
from app.core.valores import Dinheiro
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import gerar_hash
from app.vendas.excecoes import MotivoObrigatorio, VendaJaCancelada
from app.vendas.modelos import Venda
from app.vendas.repositorio import RepositorioVendas
from app.vendas.servico import ServicoVendas

REGISTRO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CANCELAMENTO = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
HOJE = date(2026, 10, 8)


def _marmita() -> ItemVendavel:
    return ItemVendavel(
        item_id=1,
        nome_prato="Frango grelhado",
        nome_proteina="Frango",
        formato=Formato.MARMITA,
        preco=Decimal("22.00"),
        gramas_por_porcao=150,
    )


def _venda() -> Venda:
    return Venda.registrar(
        estabelecimento_id=1,
        item=_marmita(),
        quantidade=2,
        usuario_id=1,
        chave="chave-cancelamento",
        agora=REGISTRO,
    )


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante


# Unitários: só a entidade, sem banco.


@pytest.mark.parametrize("motivo", ["", "   "])
def test_CA_16_cancelamento_sem_motivo_e_recusado(motivo: str) -> None:
    venda = _venda()

    with pytest.raises(MotivoObrigatorio):
        venda.cancelar(por=2, motivo=motivo, agora=CANCELAMENTO)

    assert venda.cancelada_em is None
    assert venda.motivo_cancelamento is None


def test_CA_17_venda_ja_cancelada_nao_e_cancelada_de_novo() -> None:
    venda = _venda()
    venda.cancelar(por=2, motivo="Lançada com toque errado", agora=CANCELAMENTO)

    with pytest.raises(VendaJaCancelada):
        venda.cancelar(por=3, motivo="Outro motivo", agora=CANCELAMENTO + timedelta(hours=1))

    # Os dados do primeiro cancelamento ficam intactos (RN-25).
    assert venda.cancelada_em == CANCELAMENTO
    assert venda.cancelada_por == 2
    assert venda.motivo_cancelamento == "Lançada com toque errado"


# Integração: banco real, transação desfeita no fim do teste.


async def _usuario(sessao: AsyncSession, login: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _item(sessao: AsyncSession, nome_prato: str) -> ItemCardapio:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Proteína {nome_prato}")
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


async def test_cancelar_venda_de_data_passada(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    admin = await _usuario(sessao, "admin-cancela", Perfil.ADMIN)
    operador = await _usuario(sessao, "operador-cancela", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    registro = await _servico(sessao, estabelecimento_id, RelogioFixo(REGISTRO)).registrar(
        item.id, 2, "chave-data-passada", operador.id
    )

    # Cancelado doze dias depois: a data da venda não impede (RN-22).
    cancelada = await _servico(sessao, estabelecimento_id, RelogioFixo(CANCELAMENTO)).cancelar(
        registro.venda.id, admin.id, "Venda duplicada no sistema"
    )

    assert cancelada.cancelada_em == CANCELAMENTO
    assert cancelada.registrada_em == REGISTRO


async def test_cancelamento_nao_remove_a_linha(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    admin = await _usuario(sessao, "admin-linha", Perfil.ADMIN)
    operador = await _usuario(sessao, "operador-linha", Perfil.OPERADOR)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    servico = _servico(sessao, estabelecimento_id, RelogioFixo(REGISTRO))
    registro = await servico.registrar(item.id, 2, "chave-linha", operador.id)
    total_antes = await sessao.scalar(select(func.count()).select_from(Venda))

    await _servico(sessao, estabelecimento_id, RelogioFixo(CANCELAMENTO)).cancelar(
        registro.venda.id, admin.id, "Lançamento errado"
    )

    # Nenhuma linha some, e a da venda guarda instante, autor e motivo (RN-23).
    total_depois = await sessao.scalar(select(func.count()).select_from(Venda))
    assert total_depois == total_antes
    linha = await sessao.scalar(select(Venda).where(Venda.id == registro.venda.id))
    await sessao.refresh(linha)
    assert linha.cancelada_em == CANCELAMENTO
    assert linha.cancelada_por == admin.id
    assert linha.motivo_cancelamento == "Lançamento errado"
    # Quantidade e snapshot não mudam: a linha inteira é cancelada, nada é corrigido (RN-24).
    assert linha.quantidade == 2
    assert linha.preco_unitario == Decimal("22.00")
    assert linha.valor_total == Decimal("44.00")


async def test_cancelar_venda_inexistente_e_nao_encontrada(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    admin = await _usuario(sessao, "admin-inexistente", Perfil.ADMIN)

    with pytest.raises(NaoEncontrado):
        await _servico(sessao, estabelecimento_id, RelogioFixo(CANCELAMENTO)).cancelar(
            999_999, admin.id, "Motivo qualquer"
        )


async def test_cancelamento_concorrente_espera_a_trava_e_e_recusado(engine) -> None:
    """Dois ADMINs cancelando a mesma venda (risco da T-27). A primeira transação segura a linha
    sem commitar; a segunda precisa esperar, e depois do commit encontra a venda já cancelada.
    Sem a trava `FOR UPDATE`, a segunda não espera a leitura e grava por cima sem recusar.
    Grava de verdade, em sessões com commit, e limpa tudo no fim."""
    fabrica = criar_fabrica_sessoes(engine)
    sufixo = uuid.uuid4().hex[:8]
    login_operador = f"op{sufixo}"
    login_admin_a = f"adA{sufixo}"
    login_admin_b = f"adB{sufixo}"
    async with fabrica() as sessao, sessao.begin():
        estabelecimento_id = await estabelecimento_atual(sessao)
        operador = await _usuario(sessao, login_operador, Perfil.OPERADOR)
        admin_a = await _usuario(sessao, login_admin_a, Perfil.ADMIN)
        admin_b = await _usuario(sessao, login_admin_b, Perfil.ADMIN)
        item = await _item(sessao, f"Prato {sufixo}")
        await _cardapio_de_hoje(sessao, item)
        registro = await _servico(sessao, estabelecimento_id, RelogioFixo(REGISTRO)).registrar(
            item.id, 2, f"chave-{sufixo}", operador.id
        )
        venda_id, item_id = registro.venda.id, item.id
        admin_a_id, admin_b_id = admin_a.id, admin_b.id

    async def cancelar_em_outra_sessao(admin_id: int, motivo: str) -> None:
        async with fabrica() as sessao, sessao.begin():
            servico = _servico(sessao, estabelecimento_id, RelogioFixo(CANCELAMENTO))
            await servico.cancelar(venda_id, admin_id, motivo)

    try:
        async with fabrica() as sessao_a, sessao_a.begin():
            servico_a = _servico(sessao_a, estabelecimento_id, RelogioFixo(CANCELAMENTO))
            await servico_a.cancelar(venda_id, admin_a_id, "Motivo do ADMIN A")
            # Segunda tentativa começa enquanto a primeira ainda não commitou: tem de esperar.
            tentativa_b = asyncio.create_task(
                cancelar_em_outra_sessao(admin_b_id, "Motivo do ADMIN B")
            )
            await asyncio.sleep(0.3)
            assert not tentativa_b.done()
        # Ao sair do bloco, a primeira commitou. A segunda relê a venda já cancelada e recusa.
        with pytest.raises(VendaJaCancelada):
            await tentativa_b

        async with fabrica() as sessao:
            linha = await sessao.scalar(select(Venda).where(Venda.id == venda_id))
            assert linha.motivo_cancelamento == "Motivo do ADMIN A"
    finally:
        async with fabrica() as sessao, sessao.begin():
            await sessao.execute(delete(Venda).where(Venda.id == venda_id))
            await sessao.execute(delete(cardapio_item).where(cardapio_item.c.item_id == item_id))
            await sessao.execute(delete(CardapioData).where(CardapioData.data == HOJE))
            await sessao.execute(delete(ItemCardapio).where(ItemCardapio.id == item_id))
            await sessao.execute(delete(Prato).where(Prato.nome == f"Prato {sufixo}"))
            await sessao.execute(
                delete(Proteina).where(Proteina.nome == f"Proteína Prato {sufixo}")
            )
            await sessao.execute(
                delete(Usuario).where(
                    Usuario.login.in_([login_operador, login_admin_a, login_admin_b])
                )
            )
