"""Fechamento do dia pela API: GET /api/fechamento/dia, só ADMIN (RN-28, RN-32, RN-33, RN-61).

O relógio fixo define o dia corrente: em 08/10 o dia 15/09 é passado, e em 15/09 ele é o dia de
hoje, com o fechamento parcial. 15:00 UTC é 12:00 em São Paulo.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemVendavel
from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao
from app.vendas.modelos import Venda

DIA_PASSADO = date(2026, 9, 15)
DIA_DO_TESTE = datetime(2026, 9, 15, 15, 0, tzinfo=UTC)  # 12:00 em São Paulo, dia 15/09
HOJE_MAIS_TARDE = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)  # dia 08/10: 15/09 já passou
ROTA = "/api/fechamento/dia"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def agora(self) -> datetime:
        return self._instante


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


async def _entrar_como(
    app: FastAPI,
    cliente: AsyncClient,
    sessao: AsyncSession,
    usuario: Usuario,
    instante: datetime,
) -> None:
    relogio = RelogioFixo(instante)
    app.dependency_overrides[obter_relogio] = lambda: relogio
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        relogio,
    )
    cliente.cookies.set(NOME_COOKIE_SESSAO, await servico.abrir(usuario))


async def _cadastro(sessao: AsyncSession) -> dict[str, ItemVendavel]:
    """Frango grelhado de 150 g: PF a R$ 18,00 e marmita a R$ 22,00."""
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


async def test_CA_23_admin_consulta_fechamento_de_data_passada(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", "Operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    await _vender(sessao, operador, itens["pf"], 2, DIA_DO_TESTE, "ca23-pf")
    await _vender(sessao, operador, itens["marmita"], 1, DIA_DO_TESTE, "ca23-marmita")
    cancelada = await _vender(sessao, operador, itens["pf"], 1, DIA_DO_TESTE, "ca23-cancelada")
    cancelada.cancelar(por=admin.id, motivo="Erro", agora=HOJE_MAIS_TARDE)
    await sessao.flush()
    await _entrar_como(app, cliente, sessao, admin, HOJE_MAIS_TARDE)

    resposta = await cliente.get(ROTA, params={"data": DIA_PASSADO.isoformat()})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["data"] == "2026-09-15"
    assert corpo["parcial"] is False
    # Totais sem a cancelada: 3 unidades, R$ 58,00 (RN-28).
    assert corpo["total_unidades"] == 3
    assert corpo["faturamento_total"] == "58.00"
    assert corpo["faturamento_por_formato"] == [
        {"formato": "MARMITA", "valor": "22.00"},
        {"formato": "PF", "valor": "36.00"},
    ]


async def test_CA_18_cancelamento_de_data_passada_altera_aquela_data(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", "Operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    # 78 unidades de base em lançamentos de até 20 (RN-14), e um lançamento de 2 a cancelar.
    for indice in range(4):
        await _vender(sessao, operador, itens["pf"], 19, DIA_DO_TESTE, f"ca18-base-{indice}")
    await _vender(sessao, operador, itens["pf"], 2, DIA_DO_TESTE, "ca18-base-resto")
    alvo = await _vender(sessao, operador, itens["pf"], 2, DIA_DO_TESTE, "ca18-alvo")
    await _entrar_como(app, cliente, sessao, admin, HOJE_MAIS_TARDE)
    antes = await cliente.get(ROTA, params={"data": DIA_PASSADO.isoformat()})
    assert antes.json()["total_unidades"] == 80

    cancelamento = await cliente.post(
        f"/api/vendas/{alvo.id}/cancelar", json={"motivo": "lançado em dobro"}
    )
    assert cancelamento.status_code == 200
    depois = await cliente.get(ROTA, params={"data": DIA_PASSADO.isoformat()})

    # O fechamento de 15/09 passa a 78 unidades, e o cancelamento aparece com quem cancelou.
    corpo = depois.json()
    assert corpo["total_unidades"] == 78
    assert len(corpo["cancelamentos_posteriores"]) == 1
    cancelado = corpo["cancelamentos_posteriores"][0]
    assert cancelado["venda_id"] == alvo.id
    assert cancelado["cancelada_por"] == "Admin"
    assert cancelado["motivo_cancelamento"] == "lançado em dobro"
    assert cancelado["cancelada_em"] is not None


async def test_CA_14_venda_cancelada_sai_do_fechamento(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", "Operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    venda = await _vender(sessao, operador, itens["pf"], 2, DIA_DO_TESTE, "ca14")
    await _entrar_como(app, cliente, sessao, admin, DIA_DO_TESTE)
    antes = await cliente.get(ROTA)
    assert antes.json()["total_unidades"] == 2
    assert antes.json()["parcial"] is True

    cancelamento = await cliente.post(
        f"/api/vendas/{venda.id}/cancelar", json={"motivo": "cliente desistiu"}
    )
    assert cancelamento.status_code == 200
    depois = await cliente.get(ROTA)

    # As 2 unidades saem do fechamento do dia (RN-28). Cancelada no mesmo dia, não é posterior.
    assert depois.json()["total_unidades"] == 0
    assert depois.json()["cancelamentos_posteriores"] == []


async def test_CA_31_corrigir_quantidade_exige_cancelar_e_registrar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", "Operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    errada = await _vender(sessao, operador, itens["pf"], 3, DIA_DO_TESTE, "ca31-errada")
    certa = await _vender(sessao, operador, itens["pf"], 2, DIA_DO_TESTE, "ca31-certa")
    await _entrar_como(app, cliente, sessao, admin, DIA_DO_TESTE)
    cancelamento = await cliente.post(
        f"/api/vendas/{errada.id}/cancelar", json={"motivo": "quantidade errada"}
    )
    assert cancelamento.status_code == 200

    resposta = await cliente.get(ROTA)

    assert resposta.json()["total_unidades"] == 2
    # As duas linhas continuam no histórico: a cancelada não some (RN-23).
    ids = (await sessao.scalars(select(Venda.id).where(Venda.id.in_([errada.id, certa.id])))).all()
    assert set(ids) == {errada.id, certa.id}
