"""Faturamento por formato e cancelamentos posteriores do fechamento (RN-31, RN-32, RN-61).

Os valores saem do snapshot da venda (preço × quantidade), somados no banco e entregues como
`Dinheiro`. O dia 15/09 em São Paulo é o intervalo UTC `[15/09 03:00, 16/09 03:00)`.
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
    cancelamentos_posteriores,
    faturamento_por_formato,
    faturamento_total,
)
from app.vendas.modelos import Venda

DIA = date(2026, 9, 15)
NO_DIA = datetime(2026, 9, 15, 15, 0, tzinfo=UTC)  # 12:00 em São Paulo
DEPOIS_DO_DIA = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
MESMO_DIA_TARDE = datetime(2026, 9, 15, 20, 0, tzinfo=UTC)  # 17:00 em São Paulo


async def _usuario(sessao: AsyncSession, login: str, nome: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=nome,
        login=login,
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _cadastro(sessao: AsyncSession) -> dict[str, ItemVendavel]:
    """Frango grelhado de 150 g em PF a R$ 18,00 e em marmita a R$ 22,00."""
    estabelecimento_id = await estabelecimento_atual(sessao)
    frango = Proteina.criar(estabelecimento_id=estabelecimento_id, nome="Frango")
    sessao.add(frango)
    await sessao.flush()
    grelhado = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome="Frango grelhado",
        proteina_id=frango.id,
        gramas_por_porcao=150,
    )
    sessao.add(grelhado)
    await sessao.flush()
    pf = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=grelhado.id,
        formato=Formato.PF,
        preco=Dinheiro("18.00"),
    )
    marmita = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=grelhado.id,
        formato=Formato.MARMITA,
        preco=Dinheiro("22.00"),
    )
    sessao.add_all([pf, marmita])
    await sessao.flush()
    return {
        "pf": ItemVendavel(
            item_id=pf.id,
            nome_prato="Frango grelhado",
            nome_proteina="Frango",
            formato=Formato.PF,
            preco=Decimal("18.00"),
            gramas_por_porcao=150,
        ),
        "marmita": ItemVendavel(
            item_id=marmita.id,
            nome_prato="Frango grelhado",
            nome_proteina="Frango",
            formato=Formato.MARMITA,
            preco=Decimal("22.00"),
            gramas_por_porcao=150,
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


async def test_CA_37_fechamento_separa_faturamento_por_formato(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    operador = await _usuario(sessao, "operador-faturamento", "Operador", Perfil.OPERADOR)
    itens = await _cadastro(sessao)
    await _vender(sessao, operador, itens["pf"], 10, NO_DIA, "ca37-pf")
    await _vender(sessao, operador, itens["marmita"], 4, NO_DIA, "ca37-marmita")

    inicio, fim = _intervalo(DIA)
    por_formato = await faturamento_por_formato(sessao, estabelecimento_id, inicio, fim)
    total = await faturamento_total(sessao, estabelecimento_id, inicio, fim)

    valores = {linha.formato: linha.valor.valor for linha in por_formato}
    assert valores == {Formato.PF: Decimal("180.00"), Formato.MARMITA: Decimal("88.00")}
    assert total.valor == Decimal("268.00")


async def test_CA_67_fechamento_informa_cancelamento_posterior(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    operador = await _usuario(sessao, "operador-ca67", "Operador", Perfil.OPERADOR)
    carla = await _usuario(sessao, "carla", "Carla", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    venda = await _vender(sessao, operador, itens["pf"], 2, NO_DIA, "ca67")
    venda.cancelar(por=carla.id, motivo="lançado em dobro", agora=DEPOIS_DO_DIA)
    await sessao.flush()

    inicio, fim = _intervalo(DIA)
    posteriores = await cancelamentos_posteriores(sessao, estabelecimento_id, inicio, fim)
    total = await faturamento_total(sessao, estabelecimento_id, inicio, fim)

    assert len(posteriores) == 1
    cancelamento = posteriores[0]
    assert cancelamento.venda_id == venda.id
    assert cancelamento.cancelada_por_id == carla.id
    assert cancelamento.cancelada_em == DEPOIS_DO_DIA
    assert cancelamento.motivo_cancelamento == "lançado em dobro"
    assert cancelamento.valor_total.valor == Decimal("36.00")
    # Os totais de 15/09 já não contam a venda cancelada (RN-32).
    assert total.valor == Decimal("0")


async def test_cancelamento_no_mesmo_dia_nao_e_posterior(sessao: AsyncSession) -> None:
    estabelecimento_id = await estabelecimento_atual(sessao)
    operador = await _usuario(sessao, "operador-mesmo-dia", "Operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin-mesmo-dia", "Admin", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    venda = await _vender(sessao, operador, itens["pf"], 1, NO_DIA, "mesmo-dia")
    venda.cancelar(por=admin.id, motivo="Erro de digitação", agora=MESMO_DIA_TARDE)
    await sessao.flush()

    inicio, fim = _intervalo(DIA)

    # Cancelada no próprio dia: não é "posterior" (RN-61), e os totais já a excluem (RN-28).
    assert await cancelamentos_posteriores(sessao, estabelecimento_id, inicio, fim) == []
    assert (await faturamento_total(sessao, estabelecimento_id, inicio, fim)).valor == Decimal("0")
