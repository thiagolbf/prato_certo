"""Serviço de proteínas: nome único, desativação protegida e reativação (RN-01, RN-49, RN-58).

Só orquestra: a regra de nome e de desativação está na entidade e no repositório. A checagem
de dependentes e a desativação acontecem na mesma transação, com a proteína travada.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.catalogo.modelos import Proteina
from app.catalogo.repositorio import RepositorioProteinas
from app.core.excecoes import Conflito, NaoEncontrado

logger = logging.getLogger("app.catalogo")
MENSAGEM_NOME_REPETIDO = "Já existe uma proteína com esse nome."
MENSAGEM_NOME_DESATIVADO = (
    "Já existe uma proteína desativada com esse nome. Reative-a em vez de criar outra."
)


@dataclass(frozen=True)
class ProteinaLeitura:
    id: int
    nome: str
    ativo: bool
    pratos_ativos: int


class ServicoProteinas:
    def __init__(self, repositorio: RepositorioProteinas) -> None:
        self._repositorio = repositorio

    async def listar(self, incluir_desativadas: bool) -> list[ProteinaLeitura]:
        return [
            ProteinaLeitura(
                id=proteina.id,
                nome=proteina.nome,
                ativo=proteina.ativo,
                pratos_ativos=total,
            )
            for proteina, total in await self._repositorio.listar(incluir_desativadas)
        ]

    async def criar(self, nome: str) -> ProteinaLeitura:
        await self._exigir_nome_livre(nome, ignorando=None)
        proteina = Proteina.criar(
            estabelecimento_id=self._repositorio.estabelecimento_id, nome=nome
        )
        self._repositorio.adicionar(proteina)
        try:
            await self._repositorio.persistir()
        except IntegrityError as erro:
            # Corrida: outro cadastro com o mesmo nome entrou entre a checagem e o insert.
            raise Conflito(MENSAGEM_NOME_REPETIDO) from erro
        logger.info("proteina criada", extra={"proteina_id": proteina.id})
        return ProteinaLeitura(id=proteina.id, nome=proteina.nome, ativo=True, pratos_ativos=0)

    async def renomear(self, proteina_id: int, nome: str) -> ProteinaLeitura:
        proteina = await self._buscar(proteina_id)
        await self._exigir_nome_livre(nome, ignorando=proteina.id)
        proteina.renomear(nome)
        return await self._leitura(proteina)

    async def desativar(self, proteina_id: int) -> ProteinaLeitura:
        proteina = await self._repositorio.buscar_por_id_para_atualizar(proteina_id)
        if proteina is None:
            raise NaoEncontrado("Proteína não encontrada.")
        dependentes = await self._repositorio.pratos_ativos_que_usam(proteina.id)
        if dependentes:
            raise Conflito(
                "Não é possível desativar: usada pelo prato ativo "
                + ", ".join(dependentes)
                + ". Desative esses pratos antes."
            )
        proteina.desativar()
        logger.info("proteina desativada", extra={"proteina_id": proteina.id})
        return await self._leitura(proteina)

    async def reativar(self, proteina_id: int) -> ProteinaLeitura:
        proteina = await self._buscar(proteina_id)
        proteina.reativar()
        return await self._leitura(proteina)

    async def _buscar(self, proteina_id: int) -> Proteina:
        proteina = await self._repositorio.buscar_por_id(proteina_id)
        if proteina is None:
            raise NaoEncontrado("Proteína não encontrada.")
        return proteina

    async def _exigir_nome_livre(self, nome: str, ignorando: int | None) -> None:
        existente = await self._repositorio.buscar_por_nome(nome)
        if existente is not None and existente.id != ignorando:
            mensagem = MENSAGEM_NOME_REPETIDO if existente.ativo else MENSAGEM_NOME_DESATIVADO
            raise Conflito(mensagem)

    async def _leitura(self, proteina: Proteina) -> ProteinaLeitura:
        return ProteinaLeitura(
            id=proteina.id,
            nome=proteina.nome,
            ativo=proteina.ativo,
            pratos_ativos=await self._repositorio.contar_pratos_ativos(proteina.id),
        )
