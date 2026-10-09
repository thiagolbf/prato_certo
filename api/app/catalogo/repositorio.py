"""Repositório do catálogo: acesso às tabelas `proteina`, `prato`, `item_cardapio` e
`cardapio_data` (ADR-003, RN-41).

Recebe o `estabelecimento_id` no construtor e filtra toda consulta por ele.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalogo.modelos import CardapioData, Formato, ItemCardapio, Prato, Proteina


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

    async def buscar_por_id_para_atualizar(self, prato_id: int) -> Prato | None:
        """Trava o prato até o fim da transação; criação de item e desativação se serializam."""
        return await self._sessao.scalar(
            select(Prato)
            .where(
                Prato.estabelecimento_id == self._estabelecimento_id,
                Prato.id == prato_id,
            )
            .with_for_update()
        )

    def adicionar(self, prato: Prato) -> None:
        self._sessao.add(prato)

    async def persistir(self) -> None:
        await self._sessao.flush()


class RepositorioItens:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    async def listar(self, incluir_desativados: bool) -> Sequence[tuple[ItemCardapio, str, int]]:
        consulta = (
            select(ItemCardapio, Prato.nome, Prato.gramas_por_porcao)
            .join(Prato, Prato.id == ItemCardapio.prato_id)
            .where(ItemCardapio.estabelecimento_id == self._estabelecimento_id)
            .order_by(Prato.nome, ItemCardapio.formato)
        )
        if not incluir_desativados:
            consulta = consulta.where(ItemCardapio.ativo.is_(True))
        return (await self._sessao.execute(consulta)).all()

    async def buscar_por_id(self, item_id: int) -> ItemCardapio | None:
        return await self._sessao.scalar(
            select(ItemCardapio).where(
                ItemCardapio.estabelecimento_id == self._estabelecimento_id,
                ItemCardapio.id == item_id,
            )
        )

    async def buscar_por_prato_e_formato(
        self, prato_id: int, formato: Formato
    ) -> ItemCardapio | None:
        # Vale também para desativado: o par não se repete (RN-59).
        return await self._sessao.scalar(
            select(ItemCardapio).where(
                ItemCardapio.estabelecimento_id == self._estabelecimento_id,
                ItemCardapio.prato_id == prato_id,
                ItemCardapio.formato == formato,
            )
        )

    def adicionar(self, item: ItemCardapio) -> None:
        self._sessao.add(item)

    async def persistir(self) -> None:
        await self._sessao.flush()


class RepositorioCardapios:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    @property
    def estabelecimento_id(self) -> int:
        return self._estabelecimento_id

    async def buscar_proprio(self, data: date) -> CardapioData | None:
        """Cardápio gravado para a data, com os itens carregados (ADR-009)."""
        return await self._sessao.scalar(
            select(CardapioData)
            .where(
                CardapioData.estabelecimento_id == self._estabelecimento_id,
                CardapioData.data == data,
            )
            .options(selectinload(CardapioData.itens))
        )

    async def mais_recente_anterior(self, data: date) -> CardapioData | None:
        """Cardápio gravado mais recente de data anterior a `data`, com os itens carregados.

        Data futura nunca entra aqui: um cardápio de amanhã não é herdado hoje (RN-50).
        """
        return await self._sessao.scalar(
            select(CardapioData)
            .where(
                CardapioData.estabelecimento_id == self._estabelecimento_id,
                CardapioData.data < data,
            )
            .order_by(CardapioData.data.desc())
            .limit(1)
            .options(selectinload(CardapioData.itens))
        )

    async def buscar_itens(self, item_ids: Sequence[int]) -> Sequence[ItemCardapio]:
        """Itens pedidos do estabelecimento; ativos ou não, a entidade decide (RN-12)."""
        return (
            await self._sessao.scalars(
                select(ItemCardapio).where(
                    ItemCardapio.estabelecimento_id == self._estabelecimento_id,
                    ItemCardapio.id.in_(item_ids),
                )
            )
        ).all()

    def adicionar(self, cardapio: CardapioData) -> None:
        self._sessao.add(cardapio)

    async def persistir(self) -> None:
        await self._sessao.flush()

    async def itens_vendaveis(
        self, item_ids: Sequence[int]
    ) -> Sequence[tuple[ItemCardapio, str, str, int]]:
        """Itens ativos com nome do prato, da proteína e gramagem, numa consulta (RN-12, RN-19)."""
        if not item_ids:
            return []
        return (
            await self._sessao.execute(
                select(ItemCardapio, Prato.nome, Proteina.nome, Prato.gramas_por_porcao)
                .join(Prato, Prato.id == ItemCardapio.prato_id)
                .join(Proteina, Proteina.id == Prato.proteina_id)
                .where(
                    ItemCardapio.estabelecimento_id == self._estabelecimento_id,
                    ItemCardapio.id.in_(item_ids),
                    ItemCardapio.ativo.is_(True),
                )
                .order_by(Prato.nome, ItemCardapio.formato)
            )
        ).all()
