"""Repositório do catálogo: acesso às tabelas `proteina` e `prato` (ADR-003, RN-41).

Recebe o `estabelecimento_id` no construtor e filtra toda consulta por ele.
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina


class RepositorioProteinas:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    @property
    def estabelecimento_id(self) -> int:
        return self._estabelecimento_id

    async def listar(self, incluir_desativadas: bool) -> Sequence[tuple[Proteina, int]]:
        pratos_ativos = (
            select(func.count(Prato.id))
            .where(Prato.proteina_id == Proteina.id, Prato.ativo.is_(True))
            .scalar_subquery()
        )
        consulta = (
            select(Proteina, pratos_ativos)
            .where(Proteina.estabelecimento_id == self._estabelecimento_id)
            .order_by(Proteina.nome)
        )
        if not incluir_desativadas:
            consulta = consulta.where(Proteina.ativo.is_(True))
        return (await self._sessao.execute(consulta)).all()

    async def buscar_por_id(self, proteina_id: int) -> Proteina | None:
        return await self._sessao.scalar(
            select(Proteina).where(
                Proteina.estabelecimento_id == self._estabelecimento_id,
                Proteina.id == proteina_id,
            )
        )

    async def buscar_por_id_para_atualizar(self, proteina_id: int) -> Proteina | None:
        """Trava a proteína até o fim da transação: um prato novo que a referencie espera.

        Sem isso, a checagem de pratos ativos e a desativação poderiam se atravessar (RN-58).
        """
        return await self._sessao.scalar(
            select(Proteina)
            .where(
                Proteina.estabelecimento_id == self._estabelecimento_id,
                Proteina.id == proteina_id,
            )
            .with_for_update()
        )

    async def buscar_por_nome(self, nome: str) -> Proteina | None:
        # Sem diferenciar maiúsculas nem espaços nas pontas, como o índice (RN-01, RN-59).
        return await self._sessao.scalar(
            select(Proteina).where(
                Proteina.estabelecimento_id == self._estabelecimento_id,
                func.lower(func.trim(Proteina.nome)) == func.lower(func.trim(nome)),
            )
        )

    async def pratos_ativos_que_usam(self, proteina_id: int) -> Sequence[str]:
        return (
            await self._sessao.scalars(
                select(Prato.nome)
                .where(
                    Prato.estabelecimento_id == self._estabelecimento_id,
                    Prato.proteina_id == proteina_id,
                    Prato.ativo.is_(True),
                )
                .order_by(Prato.nome)
            )
        ).all()

    async def contar_pratos_ativos(self, proteina_id: int) -> int:
        return len(await self.pratos_ativos_que_usam(proteina_id))

    def adicionar(self, proteina: Proteina) -> None:
        self._sessao.add(proteina)

    async def persistir(self) -> None:
        await self._sessao.flush()


class RepositorioPratos:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    @property
    def estabelecimento_id(self) -> int:
        return self._estabelecimento_id

    async def listar(self, incluir_desativados: bool) -> Sequence[tuple[Prato, str, int]]:
        itens_ativos = (
            select(func.count(ItemCardapio.id))
            .where(ItemCardapio.prato_id == Prato.id, ItemCardapio.ativo.is_(True))
            .scalar_subquery()
        )
        consulta = (
            select(Prato, Proteina.nome, itens_ativos)
            .join(Proteina, Proteina.id == Prato.proteina_id)
            .where(Prato.estabelecimento_id == self._estabelecimento_id)
            .order_by(Prato.nome)
        )
        if not incluir_desativados:
            consulta = consulta.where(Prato.ativo.is_(True))
        return (await self._sessao.execute(consulta)).all()

    async def buscar_por_id(self, prato_id: int) -> Prato | None:
        return await self._sessao.scalar(
            select(Prato).where(
                Prato.estabelecimento_id == self._estabelecimento_id,
                Prato.id == prato_id,
            )
        )

    async def buscar_por_nome(self, nome: str) -> Prato | None:
        # Sem diferenciar maiúsculas nem espaços nas pontas (RN-59).
        return await self._sessao.scalar(
            select(Prato).where(
                Prato.estabelecimento_id == self._estabelecimento_id,
                func.lower(func.trim(Prato.nome)) == func.lower(func.trim(nome)),
            )
        )

    async def itens_ativos_do_prato(self, prato_id: int) -> Sequence[Formato]:
        return (
            await self._sessao.scalars(
                select(ItemCardapio.formato)
                .where(
                    ItemCardapio.estabelecimento_id == self._estabelecimento_id,
                    ItemCardapio.prato_id == prato_id,
                    ItemCardapio.ativo.is_(True),
                )
                .order_by(ItemCardapio.formato)
            )
        ).all()

    def adicionar(self, prato: Prato) -> None:
        self._sessao.add(prato)

    async def persistir(self) -> None:
        await self._sessao.flush()
