"""Rota do fechamento do dia: GET /api/fechamento/dia, só ADMIN (RN-32, RN-33, RN-61; ADR-006).

Routers são funções. A rota só compõe as consultas agregadas do módulo e resolve os nomes de
quem cancelou pelo serviço de identidade, em lote (ADR-001). Consulta nunca altera estado.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import Relogio, obter_relogio
from app.core.tempo import DiaOperacional
from app.identidade.dependencias import exige_admin
from app.identidade.router import servico_usuarios_da_requisicao
from app.identidade.servico_usuarios import ServicoUsuarios
from app.relatorios.consultas import (
    cancelamentos_posteriores,
    faturamento_por_formato,
    faturamento_total,
    proteina_por_tipo,
    total_unidades,
    unidades_por_item,
    unidades_por_prato,
)
from app.relatorios.schemas import (
    CancelamentoPosteriorListado,
    FaturamentoPorFormatoListado,
    FechamentoDiaListado,
    ProteinaListada,
    UnidadesPorItemListado,
    UnidadesPorPratoListado,
)

router = APIRouter(prefix="/api/fechamento", tags=["fechamento"])


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

    por_item = await unidades_por_item(sessao, estabelecimento_id, inicio, fim)
    por_prato = await unidades_por_prato(sessao, estabelecimento_id, inicio, fim)
    total = await total_unidades(sessao, estabelecimento_id, inicio, fim)
    proteinas = await proteina_por_tipo(sessao, estabelecimento_id, inicio, fim)
    formatos = await faturamento_por_formato(sessao, estabelecimento_id, inicio, fim)
    valor_total = await faturamento_total(sessao, estabelecimento_id, inicio, fim)
    posteriores = await cancelamentos_posteriores(sessao, estabelecimento_id, inicio, fim)
    nomes = await usuarios.nomes_por_id(
        {cancelamento.cancelada_por_id for cancelamento in posteriores}
    )

    return FechamentoDiaListado(
        data=dia,
        parcial=dia == corrente,
        total_unidades=total,
        unidades_por_item=[
            UnidadesPorItemListado(
                item_id=linha.item_id,
                prato_nome=linha.prato_nome,
                formato=linha.formato,
                unidades=linha.unidades,
            )
            for linha in por_item
        ],
        unidades_por_prato=[
            UnidadesPorPratoListado(prato_nome=linha.prato_nome, unidades=linha.unidades)
            for linha in por_prato
        ],
        proteina_por_tipo=[
            ProteinaListada(proteina_nome=linha.proteina_nome, gramas=linha.gramas)
            for linha in proteinas
        ],
        faturamento_por_formato=[
            FaturamentoPorFormatoListado(formato=linha.formato, valor=linha.valor.valor)
            for linha in formatos
        ],
        faturamento_total=valor_total.valor,
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
    )
