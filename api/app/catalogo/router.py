"""Rotas do catálogo: proteínas, só para ADMIN (RN-39, ADR-009).

Routers são funções; o service vem por `Depends`. A alteração de estado é só por POST (ADR-006).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.catalogo.repositorio import RepositorioProteinas
from app.catalogo.schemas import NovaProteina, ProteinaListada, RenomearProteina
from app.catalogo.servico import ProteinaLeitura, ServicoProteinas
from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.identidade.dependencias import exige_admin

router_proteinas = APIRouter(
    prefix="/api/proteinas", tags=["catálogo"], dependencies=[Depends(exige_admin)]
)


async def servico_proteinas_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
) -> ServicoProteinas:
    return ServicoProteinas(RepositorioProteinas(sessao, estabelecimento_id))


def _listada(leitura: ProteinaLeitura) -> ProteinaListada:
    return ProteinaListada(
        id=leitura.id,
        nome=leitura.nome,
        ativo=leitura.ativo,
        pratos_ativos=leitura.pratos_ativos,
    )


@router_proteinas.get("")
async def listar_proteinas(
    servico: Annotated[ServicoProteinas, Depends(servico_proteinas_da_requisicao)],
    incluir_desativadas: bool = False,
) -> list[ProteinaListada]:
    return [_listada(item) for item in await servico.listar(incluir_desativadas)]


@router_proteinas.post("", status_code=201)
async def cadastrar_proteina(
    corpo: NovaProteina,
    servico: Annotated[ServicoProteinas, Depends(servico_proteinas_da_requisicao)],
) -> ProteinaListada:
    return _listada(await servico.criar(corpo.nome))


@router_proteinas.post("/{proteina_id}/renomear")
async def renomear_proteina(
    proteina_id: int,
    corpo: RenomearProteina,
    servico: Annotated[ServicoProteinas, Depends(servico_proteinas_da_requisicao)],
) -> ProteinaListada:
    return _listada(await servico.renomear(proteina_id, corpo.nome))


@router_proteinas.post("/{proteina_id}/desativar")
async def desativar_proteina(
    proteina_id: int,
    servico: Annotated[ServicoProteinas, Depends(servico_proteinas_da_requisicao)],
) -> ProteinaListada:
    return _listada(await servico.desativar(proteina_id))


@router_proteinas.post("/{proteina_id}/reativar")
async def reativar_proteina(
    proteina_id: int,
    servico: Annotated[ServicoProteinas, Depends(servico_proteinas_da_requisicao)],
) -> ProteinaListada:
    return _listada(await servico.reativar(proteina_id))
