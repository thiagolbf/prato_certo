"""Rotas do fechamento, do dia e do mês, só ADMIN (RN-32, RN-33, RN-55, RN-61; ADR-006).

Routers são funções. As rotas só compõem as consultas agregadas do módulo e resolvem os nomes de
quem cancelou pelo serviço de identidade, em lote (ADR-001). Consulta nunca altera estado.
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import Relogio, obter_relogio
from app.core.tempo import DiaOperacional, MesOperacional
from app.core.valores import Dinheiro
from app.identidade.dependencias import exige_admin
from app.identidade.router import servico_usuarios_da_requisicao
from app.identidade.servico_usuarios import ServicoUsuarios
from app.relatorios import consultas
from app.relatorios.leitura import (
    FaturamentoPorFormato,
    ProteinaConsumida,
    UnidadesPorItem,
    UnidadesPorPrato,
)
from app.relatorios.schemas import (
    CancelamentoPosteriorListado,
    FaturamentoPorFormatoListado,
    FechamentoDiaListado,
    FechamentoMesListado,
    ProteinaListada,
    QuebraDiaListada,
    UnidadesPorItemListado,
    UnidadesPorPratoListado,
)

router = APIRouter(prefix="/api/fechamento", tags=["fechamento"])


@dataclass(frozen=True)
class _Totais:
    """Os números de um período: os mesmos para o dia e para o mês (RN-29 a RN-31)."""

    por_item: list[UnidadesPorItem]
    por_prato: list[UnidadesPorPrato]
    total_unidades: int
    proteinas: list[ProteinaConsumida]
    formatos: list[FaturamentoPorFormato]
    faturamento_total: Dinheiro


async def _totais(sessao: SessaoDaRequisicao, estabelecimento_id: int, inicio, fim) -> _Totais:
    return _Totais(
        por_item=await consultas.unidades_por_item(sessao, estabelecimento_id, inicio, fim),
        por_prato=await consultas.unidades_por_prato(sessao, estabelecimento_id, inicio, fim),
        total_unidades=await consultas.total_unidades(sessao, estabelecimento_id, inicio, fim),
        proteinas=await consultas.proteina_por_tipo(sessao, estabelecimento_id, inicio, fim),
        formatos=await consultas.faturamento_por_formato(sessao, estabelecimento_id, inicio, fim),
        faturamento_total=await consultas.faturamento_total(
            sessao, estabelecimento_id, inicio, fim
        ),
    )


def _campos_dos_totais(totais: _Totais) -> dict:
    """Os campos de totais que o dia e o mês têm em comum, já no formato da resposta."""
    return {
        "total_unidades": totais.total_unidades,
        "unidades_por_item": [
            UnidadesPorItemListado(
                item_id=linha.item_id,
                prato_nome=linha.prato_nome,
                formato=linha.formato,
                unidades=linha.unidades,
            )
            for linha in totais.por_item
        ],
        "unidades_por_prato": [
            UnidadesPorPratoListado(prato_nome=linha.prato_nome, unidades=linha.unidades)
            for linha in totais.por_prato
        ],
        "proteina_por_tipo": [
            ProteinaListada(proteina_nome=linha.proteina_nome, gramas=linha.gramas)
            for linha in totais.proteinas
        ],
        "faturamento_por_formato": [
            FaturamentoPorFormatoListado(formato=linha.formato, valor=linha.valor.valor)
            for linha in totais.formatos
        ],
        "faturamento_total": totais.faturamento_total.valor,
    }


@router.get("/dia", dependencies=[Depends(exige_admin)])
async def fechamento_do_dia(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    usuarios: Annotated[ServicoUsuarios, Depends(servico_usuarios_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
    data: date | None = None,
) -> FechamentoDiaListado:
    """Fechamento da data, padrão o dia operacional corrente. Reflete o estado atual (RN-32)."""
    corrente = DiaOperacional.corrente(relogio).data
    dia = data or corrente
    inicio, fim = DiaOperacional(dia).intervalo_utc()

    totais = await _totais(sessao, estabelecimento_id, inicio, fim)
    posteriores = await consultas.cancelamentos_posteriores(sessao, estabelecimento_id, inicio, fim)
    nomes = await usuarios.nomes_por_id(
        {cancelamento.cancelada_por_id for cancelamento in posteriores}
    )

    return FechamentoDiaListado(
        data=dia,
        parcial=dia == corrente,
        cancelamentos_posteriores=[
            CancelamentoPosteriorListado(
                venda_id=cancelamento.venda_id,
                prato_nome=cancelamento.prato_nome,
                quantidade=cancelamento.quantidade,
                valor_total=cancelamento.valor_total.valor,
                cancelada_em=cancelamento.cancelada_em,
                cancelada_por=nomes[cancelamento.cancelada_por_id],
                motivo_cancelamento=cancelamento.motivo_cancelamento,
            )
            for cancelamento in posteriores
        ],
        **_campos_dos_totais(totais),
    )


@router.get("/mes", dependencies=[Depends(exige_admin)])
async def fechamento_do_mes(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
    mes: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> FechamentoMesListado:
    """Fechamento do mês, `AAAA-MM`, padrão o mês corrente, com a quebra por dia (RN-55).

    A quebra soma no banco, convertendo o instante para o fuso do negócio (ADR-005, ADR-007).
    """
    corrente = MesOperacional.corrente(relogio)
    alvo = MesOperacional(int(mes[:4]), int(mes[5:])) if mes else corrente
    inicio, fim = alvo.intervalo_utc()

    totais = await _totais(sessao, estabelecimento_id, inicio, fim)
    quebra = await consultas.quebra_por_dia(sessao, estabelecimento_id, inicio, fim)

    return FechamentoMesListado(
        mes=f"{alvo.ano:04d}-{alvo.mes:02d}",
        parcial=alvo == corrente,
        quebra_por_dia=[
            QuebraDiaListada(
                dia=linha.dia, unidades=linha.unidades, faturamento=linha.faturamento.valor
            )
            for linha in quebra
        ],
        **_campos_dos_totais(totais),
    )
