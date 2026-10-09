"""Repositório de vendas: acesso à tabela `venda` (ADR-003, RN-41).

Recebe o `estabelecimento_id` no construtor e filtra toda consulta por ele. Não há método de
atualização de valor nem de exclusão: a venda é append-only (ADR-004).
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as insert_postgres
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.modelos import Venda


class RepositorioVendas:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    @property
    def estabelecimento_id(self) -> int:
        return self._estabelecimento_id

    async def buscar_por_id(self, venda_id: int) -> Venda | None:
        return await self._sessao.scalar(
            select(Venda).where(
                Venda.estabelecimento_id == self._estabelecimento_id,
                Venda.id == venda_id,
            )
        )

    async def buscar_por_chave(self, chave: str) -> Venda | None:
        return await self._sessao.scalar(
            select(Venda).where(
                Venda.estabelecimento_id == self._estabelecimento_id,
                Venda.chave_idempotencia == chave,
            )
        )

    async def inserir_se_nova(self, venda: Venda) -> int | None:
        """`INSERT … ON CONFLICT DO NOTHING` pela chave de idempotência (RN-18, ADR-004).

        Devolve o id da venda gravada, ou `None` quando a chave já existia. Uma gravação
        simultânea com a mesma chave espera a outra terminar e cai aqui, sem duplicar.
        """
        tabela = Venda.__table__
        valores = {coluna.name: getattr(venda, coluna.name) for coluna in tabela.columns}
        valores.pop("id")
        comando = (
            insert_postgres(tabela)
            .values(**valores)
            .on_conflict_do_nothing(index_elements=["estabelecimento_id", "chave_idempotencia"])
            .returning(tabela.c.id)
        )
        return (await self._sessao.execute(comando)).scalar_one_or_none()
