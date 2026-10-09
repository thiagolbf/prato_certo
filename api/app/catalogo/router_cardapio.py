"""Consulta do cardápio pela API (RN-08, RN-09, RN-11, RN-40, RN-42, RN-50).

`/vigente` é para qualquer perfil autenticado e usa o dia operacional do servidor (RN-17, ADR-005).
`/cardapio?data=` é só do ADMIN e indica se a data já passou. Nenhuma rota grava o cardápio:
abrir a tela nunca altera estado (RN-42, ADR-006).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.catalogo.leitura import CardapioVigente
from app.catalogo.repositorio import RepositorioCardapios
from app.catalogo.schemas import (
    CardapioDaDataListado,
    CardapioListado,
    DefinirCardapio,
    ItemVigenteListado,
)
from app.catalogo.servico_cardapio import ServicoCardapio
from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import Relogio, obter_relogio
from app.core.tempo import DiaOperacional
from app.identidade.dependencias import exige_admin, usuario_autenticado

router = APIRouter(prefix="/api/cardapio", tags=["cardápio"])


async def servico_cardapio_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
) -> ServicoCardapio:
    return ServicoCardapio(RepositorioCardapios(sessao, estabelecimento_id))


def _listado(vigente: CardapioVigente) -> CardapioListado:
    return CardapioListado(
        data=vigente.data,
        tipo=vigente.tipo,
        data_origem=vigente.data_origem,
        itens=[
            ItemVigenteListado(
                item_id=item.item_id,
                nome_prato=item.nome_prato,
                nome_proteina=item.nome_proteina,
                formato=item.formato,
                gramas_por_porcao=item.gramas_por_porcao,
                preco=item.preco,
            )
            for item in vigente.itens
        ],
    )


@router.get("/vigente", dependencies=[Depends(usuario_autenticado)])
async def cardapio_vigente_de_hoje(
    servico: Annotated[ServicoCardapio, Depends(servico_cardapio_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> CardapioListado:
    hoje = DiaOperacional.corrente(relogio)
    return _listado(await servico.cardapio_vigente(hoje.data))


@router.get("", dependencies=[Depends(exige_admin)])
async def cardapio_da_data(
    data: date,
    servico: Annotated[ServicoCardapio, Depends(servico_cardapio_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> CardapioDaDataListado:
    hoje = DiaOperacional.corrente(relogio)
    base = _listado(await servico.cardapio_vigente(data))
    return CardapioDaDataListado(**base.model_dump(), passada=data < hoje.data)


@router.post("/{data}", dependencies=[Depends(exige_admin)])
async def definir_cardapio_da_data(
    data: date,
    corpo: DefinirCardapio,
    servico: Annotated[ServicoCardapio, Depends(servico_cardapio_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> CardapioListado:
    hoje = DiaOperacional.corrente(relogio)
    return _listado(await servico.definir(data, corpo.itens, hoje.data))
