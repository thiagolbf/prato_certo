"""Rotas de vendas: registro de venda pelo ADMIN e pelo Operador (RN-39, ADR-004, ADR-006).

Routers são funções; o service vem por `Depends`. O registro é alteração de estado, por POST.
Criação responde 201; reenvio de chave já gravada responde 200 com a venda original (RN-18).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.catalogo.router_cardapio import servico_cardapio_da_requisicao
from app.catalogo.servico_cardapio import ServicoCardapio
from app.core.db import SessaoDaRequisicao
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import Relogio, obter_relogio
from app.identidade.dependencias import usuario_autenticado
from app.identidade.servico_sessao import UsuarioAutenticado
from app.vendas.leitura import VendaLeitura
from app.vendas.repositorio import RepositorioVendas
from app.vendas.schemas import NovaVenda, VendaRegistrada
from app.vendas.servico import ServicoVendas

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
