"""Agregações do fechamento no SQL: unidades, proteína e fuso do dia (RN-27 a RN-30).

As vendas são criadas pela entidade `Venda.registrar`, nos instantes exatos dos cenários. O dia
operacional 22/09 em São Paulo é o intervalo UTC `[22/09 03:00, 23/09 03:00)`.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemVendavel
from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.tempo import DiaOperacional
from app.core.valores import Dinheiro
from app.identidade.modelos import Perfil, Usuario
from app.identidade.senha import gerar_hash
from app.relatorios.consultas import (
    proteina_por_tipo,
    total_unidades,
    unidades_por_item,
    unidades_por_prato,
)
from app.relatorios.schemas import ProteinaConsumida
from app.vendas.modelos import Venda

DIA = date(2026, 9, 22)
NO_DIA = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)  # 12:00 em São Paulo


async def _usuario(sessao: AsyncSession) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome="Operador",
        login="operador-fechamento",
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=Perfil.OPERADOR,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _cadastro(sessao: AsyncSession) -> dict[str, ItemVendavel]:
    """Frango grelhado (150 g) em PF e marmita, e Bife acebolado (180 g) em PF."""
    estabelecimento_id = await estabelecimento_atual(sessao)
    frango = Proteina.criar(estabelecimento_id=estabelecimento_id, nome="Frango")
    carne = Proteina.criar(estabelecimento_id=estabelecimento_id, nome="Carne")
    sessao.add_all([frango, carne])
    await sessao.flush()
    grelhado = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Frango grelhado",
        proteina_id=frango.id,
        gramas_por_porcao=150,
    )
    bife = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Bife acebolado",
        proteina_id=carne.id,
        gramas_por_porcao=180,
    )
    sessao.add_all([grelhado, bife])
    await sessao.flush()
    itens = {
        "frango_pf": ItemCardapio.criar(
            estabelecimento_id=estabelecimento_id,
            prato_id=grelhado.id,
            formato=Formato.PF,
            preco=Dinheiro("18.00"),
        ),
        "frango_marmita": ItemCardapio.criar(
            estabelecimento_id=estabelecimento_id,
            prato_id=grelhado.id,
            formato=Formato.MARMITA,
            preco=Dinheiro("22.00"),
        ),
        "bife_pf": ItemCardapio.criar(
            estabelecimento_id=estabelecimento_id,
            prato_id=bife.id,
            formato=Formato.PF,
            preco=Dinheiro("20.00"),
        ),
    }
    sessao.add_all(itens.values())
    await sessao.flush()
    return {
        "frango_pf": ItemVendavel(
            item_id=itens["frango_pf"].id,
            nome_prato="Frango grelhado",
            nome_proteina="Frango",
            formato=Formato.PF,
            preco=Decimal("18.00"),
            gramas_por_porcao=150,
        ),
        "frango_marmita": ItemVendavel(
            item_id=itens["frango_marmita"].id,
            nome_prato="Frango grelhado",
            nome_proteina="Frango",
            formato=Formato.MARMITA,
            preco=Decimal("22.00"),
            gramas_por_porcao=150,
        ),
        "bife_pf": ItemVendavel(
            item_id=itens["bife_pf"].id,
            nome_prato="Bife acebolado",
            nome_proteina="Carne",
            formato=Formato.PF,
            preco=Decimal("20.00"),
            gramas_por_porcao=180,
        ),
    }


async def _vender(
    sessao: AsyncSession,
    usuario: Usuario,
    item: ItemVendavel,
    quantidade: int,
    agora: datetime,
    chave: str,
) -> Venda:
    venda = Venda.registrar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        item=item,
        quantidade=quantidade,
        usuario_id=usuario.id,
        chave=chave,
        agora=agora,
    )
    sessao.add(venda)
    await sessao.flush()
    return venda


def _intervalo(dia: date) -> tuple[datetime, datetime]:
    return DiaOperacional(dia).intervalo_utc()


async def test_CA_19_venda_as_2359_pertence_ao_dia_corrente(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    itens = await _cadastro(sessao)
    # 23:59 de 22/09 em São Paulo é 02:59 UTC de 23/09.
    await _vender(
        sessao,
        usuario,
        itens["frango_pf"],
        1,
        datetime(2026, 9, 23, 2, 59, tzinfo=UTC),
        "ca19",
    )

    inicio, fim = _intervalo(DIA)
    assert await total_unidades(sessao, estabelecimento_id, inicio, fim) == 1


async def test_CA_20_venda_as_0001_pertence_ao_dia_seguinte(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    itens = await _cadastro(sessao)
    # 00:01 de 23/09 em São Paulo é 03:01 UTC de 23/09: fora do dia 22/09.
    await _vender(
        sessao,
        usuario,
        itens["frango_pf"],
        1,
        datetime(2026, 9, 23, 3, 1, tzinfo=UTC),
        "ca20",
    )

    inicio, fim = _intervalo(DIA)
    assert await total_unidades(sessao, estabelecimento_id, inicio, fim) == 0
    inicio_seguinte, fim_seguinte = _intervalo(date(2026, 9, 23))
    assert await total_unidades(sessao, estabelecimento_id, inicio_seguinte, fim_seguinte) == 1


async def test_CA_21_fechamento_agrega_proteina_por_tipo(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    itens = await _cadastro(sessao)
    await _vender(sessao, usuario, itens["frango_pf"], 10, NO_DIA, "ca21-pf")
    await _vender(sessao, usuario, itens["frango_marmita"], 4, NO_DIA, "ca21-marmita")
    await _vender(sessao, usuario, itens["bife_pf"], 6, NO_DIA, "ca21-bife")

    inicio, fim = _intervalo(DIA)
    proteinas = await proteina_por_tipo(sessao, estabelecimento_id, inicio, fim)

    assert proteinas == [
        ProteinaConsumida(proteina_nome="Carne", gramas=1080),
        ProteinaConsumida(proteina_nome="Frango", gramas=2100),
    ]
    assert await total_unidades(sessao, estabelecimento_id, inicio, fim) == 20


async def test_CA_22_fechamento_distingue_pf_de_marmita(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    itens = await _cadastro(sessao)
    await _vender(sessao, usuario, itens["frango_pf"], 10, NO_DIA, "ca22-pf")
    await _vender(sessao, usuario, itens["frango_marmita"], 4, NO_DIA, "ca22-marmita")

    inicio, fim = _intervalo(DIA)
    por_item = await unidades_por_item(sessao, estabelecimento_id, inicio, fim)
    por_prato = await unidades_por_prato(sessao, estabelecimento_id, inicio, fim)

    assert {(linha.formato, linha.unidades) for linha in por_item} == {
        (Formato.PF, 10),
        (Formato.MARMITA, 4),
    }
    assert [(linha.prato_nome, linha.unidades) for linha in por_prato] == [("Frango grelhado", 14)]


async def test_venda_cancelada_nao_entra_nas_unidades(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    usuario = await _usuario(sessao)
    itens = await _cadastro(sessao)
    cancelada = await _vender(sessao, usuario, itens["frango_pf"], 3, NO_DIA, "cancelada")
    await _vender(sessao, usuario, itens["frango_pf"], 2, NO_DIA, "ativa")
    cancelada.cancelar(por=usuario.id, motivo="Lançamento errado", agora=NO_DIA)
    await sessao.flush()

    inicio, fim = _intervalo(DIA)

    assert await total_unidades(sessao, estabelecimento_id, inicio, fim) == 2
    proteinas = await proteina_por_tipo(sessao, estabelecimento_id, inicio, fim)
    assert proteinas == [ProteinaConsumida(proteina_nome="Frango", gramas=300)]
