"""Fechamento do mês: totais, quebra por dia e fuso na virada (RN-27, RN-28, RN-31, RN-55).

Os dados são os do CA-57. O mês é agosto de 2026 em São Paulo, `[01/08 03:00, 01/09 03:00)` em UTC.
O relógio fixo é 08/10, então agosto já passou e o fechamento não é parcial.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.leitura import ItemVendavel
from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.core.tempo import MesOperacional
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao
from app.relatorios.consultas import quebra_por_dia
from app.relatorios.leitura import QuebraDoDia
from app.vendas.modelos import Venda

AGOSTO = MesOperacional(2026, 8)
ROTA = "/api/fechamento/mes"
AGORA_DO_ADMIN = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
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
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, usuario: Usuario
) -> None:
    relogio = RelogioFixo(AGORA_DO_ADMIN)
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
    """Frango grelhado (150 g, PF 18,00 e marmita 22,00) e Bife acebolado (180 g, PF 20,00)."""
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


async def test_CA_57_fechamento_do_mes_soma_os_dias_sem_as_canceladas(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "operador", "Operador", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    itens = await _cadastro(sessao)
    await _vender(
        sessao, operador, itens["frango_pf"], 10, datetime(2026, 8, 5, 15, tzinfo=UTC), "a"
    )
    await _vender(
        sessao, operador, itens["frango_marmita"], 4, datetime(2026, 8, 18, 15, tzinfo=UTC), "b"
    )
    await _vender(sessao, operador, itens["bife_pf"], 6, datetime(2026, 8, 31, 15, tzinfo=UTC), "c")
    cancelada = await _vender(
        sessao, operador, itens["bife_pf"], 2, datetime(2026, 8, 31, 15, tzinfo=UTC), "d"
    )
    cancelada.cancelar(por=admin.id, motivo="Erro", agora=AGORA_DO_ADMIN)
    await _vender(
        sessao, operador, itens["frango_pf"], 5, datetime(2026, 9, 1, 15, tzinfo=UTC), "e"
    )
    await _entrar_como(app, cliente, sessao, admin)

    resposta = await cliente.get(ROTA, params={"mes": "2026-08"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["mes"] == "2026-08"
    assert corpo["parcial"] is False
    assert corpo["total_unidades"] == 20
    assert corpo["proteina_por_tipo"] == [
        {"proteina_nome": "Carne", "gramas": 1080},
        {"proteina_nome": "Frango", "gramas": 2100},
    ]
    assert corpo["faturamento_por_formato"] == [
        {"formato": "MARMITA", "valor": "88.00"},
        {"formato": "PF", "valor": "300.00"},
    ]
    assert corpo["faturamento_total"] == "388.00"
    # Quebra por dia: 05/08 com 10, 18/08 com 4, 31/08 com 6. As vendas de 01/09 ficam de fora.
    assert corpo["quebra_por_dia"] == [
        {"dia": "2026-08-05", "unidades": 10, "faturamento": "180.00"},
        {"dia": "2026-08-18", "unidades": 4, "faturamento": "88.00"},
        {"dia": "2026-08-31", "unidades": 6, "faturamento": "120.00"},
    ]


async def test_quebra_por_dia_respeita_o_fuso_na_virada(
    sessao: AsyncSession,
) -> None:
    operador = await _usuario(sessao, "operador-fuso", "Operador", Perfil.OPERADOR)
    itens = await _cadastro(sessao)
    # 23:30 de 31/08 em São Paulo é 02:30 UTC de 01/09: ainda é agosto.
    await _vender(
        sessao, operador, itens["frango_pf"], 1, datetime(2026, 9, 1, 2, 30, tzinfo=UTC), "x"
    )
    # 00:30 de 01/09 em São Paulo é 03:30 UTC de 01/09: já é setembro.
    await _vender(
        sessao, operador, itens["frango_pf"], 1, datetime(2026, 9, 1, 3, 30, tzinfo=UTC), "y"
    )
    estabelecimento_id = await estabelecimento_atual(sessao)

    inicio, fim = AGOSTO.intervalo_utc()
    quebra_agosto: list[QuebraDoDia] = await quebra_por_dia(sessao, estabelecimento_id, inicio, fim)
    inicio_setembro, fim_setembro = MesOperacional(2026, 9).intervalo_utc()
    quebra_setembro = await quebra_por_dia(
        sessao, estabelecimento_id, inicio_setembro, fim_setembro
    )

    assert [(linha.dia, linha.unidades) for linha in quebra_agosto] == [(date(2026, 8, 31), 1)]
    assert [(linha.dia, linha.unidades) for linha in quebra_setembro] == [(date(2026, 9, 1), 1)]
