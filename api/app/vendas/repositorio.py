"""Repositório de vendas: acesso à tabela `venda` (ADR-003, RN-41).

Recebe o `estabelecimento_id` no construtor e filtra toda consulta por ele. Não há método de
atualização de valor nem de exclusão: a venda é append-only (ADR-004).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
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

    async def buscar_por_id_para_cancelar(self, venda_id: int) -> Venda | None:
        """Trava a linha até o fim da transação: dois cancelamentos simultâneos se encontram
        em série, e o segundo vê a venda já cancelada (T-27, risco da tarefa)."""
        return await self._sessao.scalar(
            select(Venda)
            .where(
                Venda.estabelecimento_id == self._estabelecimento_id,
                Venda.id == venda_id,
            )
            .with_for_update()
        )

    async def listar_do_usuario_no_intervalo(
        self, usuario_id: int, inicio: datetime, fim: datetime
    ) -> list[Venda]:
        """Vendas de um usuário em `[inicio, fim)`, canceladas inclusive, mais recentes primeiro."""
        resultado = await self._sessao.scalars(
            select(Venda)
            .where(
                Venda.estabelecimento_id == self._estabelecimento_id,
                Venda.registrada_por == usuario_id,
                Venda.registrada_em >= inicio,
                Venda.registrada_em < fim,
            )
            .order_by(Venda.registrada_em.desc(), Venda.id.desc())
        )
        return list(resultado)

    async def listar_do_dia(self, inicio: datetime, fim: datetime) -> list[Venda]:
        """Todas as vendas de todos os usuários em `[inicio, fim)`, canceladas inclusive,
        na ordem em que aconteceram (RN-51)."""
        resultado = await self._sessao.scalars(
            select(Venda)
            .where(
                Venda.estabelecimento_id == self._estabelecimento_id,
                Venda.registrada_em >= inicio,
                Venda.registrada_em < fim,
            )
            .order_by(Venda.registrada_em, Venda.id)
        )
        return list(resultado)

    async def totais_do_dia(self, inicio: datetime, fim: datetime) -> tuple[int, Decimal]:
        """Unidades e valor do dia, sem as canceladas (RN-28), somados no SQL (ADR-007)."""
        unidades, valor = (
            await self._sessao.execute(
                select(
                    func.coalesce(func.sum(Venda.quantidade), 0),
                    func.coalesce(func.sum(Venda.valor_total), 0),
                ).where(
                    Venda.estabelecimento_id == self._estabelecimento_id,
                    Venda.registrada_em >= inicio,
                    Venda.registrada_em < fim,
                    Venda.cancelada_em.is_(None),
                )
            )
        ).one()
        return int(unidades), Decimal(valor)

    async def persistir(self) -> None:
        await self._sessao.flush()

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
