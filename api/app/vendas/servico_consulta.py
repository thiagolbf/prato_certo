"""Consulta das vendas de uma data para o ADMIN (RN-27, RN-28, RN-51).

Só lê: nada aqui altera estado. Os nomes de autor e de quem cancelou vêm do serviço de
identidade, em uma chamada só (ADR-001), e não do repositório dele.
"""

from datetime import date

from app.core.tempo import DiaOperacional
from app.identidade.servico_usuarios import ServicoUsuarios
from app.vendas.leitura import VendaAuditada, VendasDaData
from app.vendas.modelos import Venda
from app.vendas.repositorio import RepositorioVendas


def _auditada(venda: Venda, nomes: dict[int, str]) -> VendaAuditada:
    return VendaAuditada(
        id=venda.id,
        registrada_em=venda.registrada_em,
        prato_nome=venda.prato_nome,
        proteina_nome=venda.proteina_nome,
        formato=venda.formato,
        quantidade=venda.quantidade,
        preco_unitario=venda.preco_unitario,
        valor_total=venda.valor_total,
        autor_nome=nomes[venda.registrada_por],
        cancelada_em=venda.cancelada_em,
        cancelada_por_nome=(
            nomes[venda.cancelada_por] if venda.cancelada_por is not None else None
        ),
        motivo_cancelamento=venda.motivo_cancelamento,
    )


class ServicoConsultaVendas:
    def __init__(self, repositorio: RepositorioVendas, usuarios: ServicoUsuarios) -> None:
        self._repositorio = repositorio
        self._usuarios = usuarios

    async def da_data(self, data: date) -> VendasDaData:
        inicio, fim = DiaOperacional(data).intervalo_utc()
        vendas = await self._repositorio.listar_do_dia(inicio, fim)
        ids = {venda.registrada_por for venda in vendas}
        ids |= {venda.cancelada_por for venda in vendas if venda.cancelada_por is not None}
        nomes = await self._usuarios.nomes_por_id(ids)
        total_unidades, total_valor = await self._repositorio.totais_do_dia(inicio, fim)
        return VendasDaData(
            data=data,
            vendas=tuple(_auditada(venda, nomes) for venda in vendas),
            total_unidades=total_unidades,
            total_valor=total_valor,
        )
