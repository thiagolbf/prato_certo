"""Repositórios do módulo identidade: única porta de acesso às tabelas `usuario` e `sessao`.

Recebem o `estabelecimento_id` no construtor e filtram toda consulta por ele (ADR-003, RN-41).
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identidade.modelos import Sessao, Usuario


class RepositorioUsuarios:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    async def buscar_por_id(self, usuario_id: int) -> Usuario | None:
        return await self._sessao.scalar(
            select(Usuario).where(
                Usuario.estabelecimento_id == self._estabelecimento_id,
                Usuario.id == usuario_id,
            )
        )

    async def buscar_por_login(self, login: str) -> Usuario | None:
        # Sem diferenciar maiúsculas, como o índice único (RN-60).
        return await self._sessao.scalar(
            select(Usuario).where(
                Usuario.estabelecimento_id == self._estabelecimento_id,
                func.lower(Usuario.login) == func.lower(login),
            )
        )

    async def buscar_por_login_para_atualizar(self, login: str) -> Usuario | None:
        """Como `buscar_por_login`, mas trava a conta até o fim da transação.

        Duas tentativas simultâneas na mesma conta não podem perder uma falha (RN-37).
        """
        return await self._sessao.scalar(
            select(Usuario)
            .where(
                Usuario.estabelecimento_id == self._estabelecimento_id,
                func.lower(Usuario.login) == func.lower(login),
            )
            .with_for_update()
        )

    async def listar(self) -> Sequence[Usuario]:
        return (
            await self._sessao.scalars(
                select(Usuario)
                .where(Usuario.estabelecimento_id == self._estabelecimento_id)
                .order_by(Usuario.nome, Usuario.id)
            )
        ).all()

    def adicionar(self, usuario: Usuario) -> None:
        self._sessao.add(usuario)

    async def persistir(self) -> None:
        """Grava agora, para uma violação de unicidade aparecer aqui, e não no commit da rota."""
        await self._sessao.flush()


class RepositorioSessoes:
    def __init__(self, sessao: AsyncSession, estabelecimento_id: int) -> None:
        self._sessao = sessao
        self._estabelecimento_id = estabelecimento_id

    async def buscar_por_token_hash(self, token_hash: str) -> Sessao | None:
        return await self._sessao.scalar(
            select(Sessao).where(
                Sessao.estabelecimento_id == self._estabelecimento_id,
                Sessao.token_hash == token_hash,
            )
        )

    async def abertas_do_usuario(self, usuario_id: int) -> Sequence[Sessao]:
        return (
            await self._sessao.scalars(
                select(Sessao).where(
                    Sessao.estabelecimento_id == self._estabelecimento_id,
                    Sessao.usuario_id == usuario_id,
                    Sessao.encerrada_em.is_(None),
                )
            )
        ).all()

    def adicionar(self, sessao: Sessao) -> None:
        self._sessao.add(sessao)
