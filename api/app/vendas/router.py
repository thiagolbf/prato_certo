"""Rotas de vendas: registro de venda pelo ADMIN e pelo Operador (RN-39, ADR-004, ADR-006).

Routers são funções; o service vem por `Depends`. O registro é alteração de estado, por POST.
Criação responde 201; reenvio de chave já gravada responde 200 com a venda original (RN-18).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.catalogo.router_cardapio import servico_cardapio_da_requisicao
from app.catalogo.servico_cardapio import ServicoCardapio
from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import Relogio, obter_relogio
from app.core.tempo import FUSO
from app.identidade.dependencias import exige_admin, usuario_autenticado
from app.identidade.router import servico_usuarios_da_requisicao
from app.identidade.servico_sessao import UsuarioAutenticado
from app.identidade.servico_usuarios import ServicoUsuarios
from app.vendas.leitura import VendaAuditada, VendaLeitura, VendasDaData
from app.vendas.repositorio import RepositorioVendas
from app.vendas.schemas import (
    CancelarVenda,
    NovaVenda,
    VendaDaDataListada,
    VendaDoDia,
    VendaRegistrada,
    VendasDaDataListadas,
)
from app.vendas.servico import ServicoVendas
from app.vendas.servico_consulta import ServicoConsultaVendas

router = APIRouter(prefix="/api/vendas", tags=["vendas"])


async def servico_vendas_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    cardapio: Annotated[ServicoCardapio, Depends(servico_cardapio_da_requisicao)],
    relogio: Annotated[Relogio, Depends(obter_relogio)],
) -> ServicoVendas:
    return ServicoVendas(RepositorioVendas(sessao, estabelecimento_id), cardapio, relogio)


def _registrada(leitura: VendaLeitura) -> VendaRegistrada:
    return VendaRegistrada(
        id=leitura.id,
        prato_nome=leitura.prato_nome,
        proteina_nome=leitura.proteina_nome,
        formato=leitura.formato,
        quantidade=leitura.quantidade,
        preco_unitario=leitura.preco_unitario,
        valor_total=leitura.valor_total,
        proteina_total_g=leitura.proteina_total_g,
        registrada_em=leitura.registrada_em,
        cancelada_em=leitura.cancelada_em,
    )


@router.post("", status_code=201)
async def registrar_venda(
    corpo: NovaVenda,
    resposta: Response,
    usuario: Annotated[UsuarioAutenticado, Depends(usuario_autenticado)],
    servico: Annotated[ServicoVendas, Depends(servico_vendas_da_requisicao)],
) -> VendaRegistrada:
    resultado = await servico.registrar(
        corpo.item_id, corpo.quantidade, corpo.chave_idempotencia, usuario.id
    )
    if not resultado.criada:
        resposta.status_code = 200
    return _registrada(resultado.venda)


@router.post("/{venda_id}/cancelar")
async def cancelar_venda(
    venda_id: int,
    corpo: CancelarVenda,
    usuario: Annotated[UsuarioAutenticado, Depends(exige_admin)],
    servico: Annotated[ServicoVendas, Depends(servico_vendas_da_requisicao)],
) -> VendaRegistrada:
    """Só POST e só ADMIN: não há rota GET que cancele (RN-21, RN-42, ADR-006)."""
    return _registrada(await servico.cancelar(venda_id, usuario.id, corpo.motivo))


async def servico_consulta_da_requisicao(
    sessao: SessaoDaRequisicao,
    estabelecimento_id: Annotated[int, Depends(estabelecimento_atual)],
    usuarios: Annotated[ServicoUsuarios, Depends(servico_usuarios_da_requisicao)],
) -> ServicoConsultaVendas:
    return ServicoConsultaVendas(RepositorioVendas(sessao, estabelecimento_id), usuarios)


def _auditada_para_lista(venda: VendaAuditada) -> VendaDaDataListada:
    return VendaDaDataListada(
        id=venda.id,
        horario=venda.registrada_em.astimezone(FUSO),
        prato_nome=venda.prato_nome,
        proteina_nome=venda.proteina_nome,
        formato=venda.formato,
        quantidade=venda.quantidade,
        preco_unitario=venda.preco_unitario,
        valor_total=venda.valor_total,
        autor=venda.autor_nome,
        cancelada=venda.cancelada_em is not None,
        cancelada_por=venda.cancelada_por_nome,
        cancelada_em=venda.cancelada_em,
        motivo_cancelamento=venda.motivo_cancelamento,
    )


@router.get("", dependencies=[Depends(exige_admin)])
async def vendas_da_data(
    data: date,
    servico: Annotated[ServicoConsultaVendas, Depends(servico_consulta_da_requisicao)],
) -> VendasDaDataListadas:
    """Todas as vendas da data, com canceladas marcadas e totais sem elas (RN-51, RN-28)."""
    dados: VendasDaData = await servico.da_data(data)
    return VendasDaDataListadas(
        data=dados.data,
        vendas=[_auditada_para_lista(venda) for venda in dados.vendas],
        total_unidades=dados.total_unidades,
        total_valor=dados.total_valor,
    )


@router.get("/minhas")
async def minhas_vendas_do_dia(
    usuario: Annotated[UsuarioAutenticado, Depends(usuario_autenticado)],
    servico: Annotated[ServicoVendas, Depends(servico_vendas_da_requisicao)],
) -> list[VendaDoDia]:
    """Só as vendas de quem pede, do dia operacional, sem valores (RN-40). Leitura: GET (RN-42)."""
    return [
        VendaDoDia(
            id=venda.id,
            horario=venda.registrada_em.astimezone(FUSO),
            prato_nome=venda.prato_nome,
            proteina_nome=venda.proteina_nome,
            formato=venda.formato,
            quantidade=venda.quantidade,
            cancelada=venda.cancelada_em is not None,
        )
        for venda in await servico.minhas_do_dia(usuario.id)
    ]
