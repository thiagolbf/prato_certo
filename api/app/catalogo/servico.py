"""Serviço de proteínas: nome único, desativação protegida e reativação (RN-01, RN-49, RN-58).

Só orquestra: a regra de nome e de desativação está na entidade e no repositório. A checagem
de dependentes e a desativação acontecem na mesma transação, com a proteína travada.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.catalogo.modelos import Formato, Prato, Proteina
from app.catalogo.repositorio import RepositorioPratos, RepositorioProteinas
from app.core.excecoes import Conflito, NaoEncontrado, RegraViolada

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


MENSAGEM_PRATO_REPETIDO = "Já existe um prato com esse nome."
MENSAGEM_PRATO_DESATIVADO = (
    "Já existe um prato desativado com esse nome. Reative-o em vez de criar outro."
)
ROTULO_FORMATO = {Formato.PF: "PF", Formato.MARMITA: "Marmita"}


@dataclass(frozen=True)
class PratoLeitura:
    id: int
    nome: str
    proteina_id: int
    proteina_nome: str
    gramas_por_porcao: int
    ativo: bool
    itens_ativos: int


class ServicoPratos:
    """Pratos: nome único, proteína ativa, desativação protegida pelos itens (RN-58, RN-59)."""

    def __init__(self, pratos: RepositorioPratos, proteinas: RepositorioProteinas) -> None:
        self._pratos = pratos
        self._proteinas = proteinas

    async def listar(self, incluir_desativados: bool) -> list[PratoLeitura]:
        return [
            PratoLeitura(
                id=prato.id,
                nome=prato.nome,
                proteina_id=prato.proteina_id,
                proteina_nome=proteina_nome,
                gramas_por_porcao=prato.gramas_por_porcao,
                ativo=prato.ativo,
                itens_ativos=total,
            )
            for prato, proteina_nome, total in await self._pratos.listar(incluir_desativados)
        ]

    async def criar(self, nome: str, proteina_id: int, gramas: int) -> PratoLeitura:
        proteina = await self._proteina_ativa(proteina_id)
        await self._exigir_nome_livre(nome, ignorando=None)
        try:
            prato = Prato.criar(
                estabelecimento_id=self._pratos.estabelecimento_id,
                nome=nome,
                proteina_id=proteina.id,
                gramas_por_porcao=gramas,
            )
        except ValueError as erro:
            raise RegraViolada(str(erro)) from erro
        self._pratos.adicionar(prato)
        try:
            await self._pratos.persistir()
        except IntegrityError as erro:
            # Corrida: outro cadastro com o mesmo nome entrou entre a checagem e o insert.
            raise Conflito(MENSAGEM_PRATO_REPETIDO) from erro
        logger.info("prato criado", extra={"prato_id": prato.id})
        return await self._leitura(prato, proteina.nome)

    async def renomear(self, prato_id: int, nome: str) -> PratoLeitura:
        prato = await self._buscar(prato_id)
        await self._exigir_nome_livre(nome, ignorando=prato.id)
        prato.renomear(nome)
        return await self._leitura(prato)

    async def alterar_gramagem(self, prato_id: int, gramas: int) -> PratoLeitura:
        """Vale dali em diante; as vendas já registradas guardam o snapshot (RN-06, ADR-004)."""
        prato = await self._buscar(prato_id)
        try:
            prato.alterar_gramagem(gramas)
        except ValueError as erro:
            raise RegraViolada(str(erro)) from erro
        return await self._leitura(prato)

    async def desativar(self, prato_id: int) -> PratoLeitura:
        prato = await self._buscar(prato_id)
        itens = await self._pratos.itens_ativos_do_prato(prato.id)
        if itens:
            rotulos = ", ".join(f"{prato.nome} - {ROTULO_FORMATO[formato]}" for formato in itens)
            raise Conflito(
                f"Não é possível desativar: itens ativos {rotulos}. Desative esses itens antes."
            )
        prato.desativar()
        logger.info("prato desativado", extra={"prato_id": prato.id})
        return await self._leitura(prato)

    async def reativar(self, prato_id: int) -> PratoLeitura:
        prato = await self._buscar(prato_id)
        proteina = await self._proteinas.buscar_por_id(prato.proteina_id)
        if proteina is None or not proteina.ativo:
            # Reativar um prato de proteína desativada criaria prato ativo sem proteína (RN-58).
            raise RegraViolada("A proteína do prato está desativada. Reative-a antes.")
        prato.reativar()
        return await self._leitura(prato)

    async def _proteina_ativa(self, proteina_id: int) -> Proteina:
        proteina = await self._proteinas.buscar_por_id_para_atualizar(proteina_id)
        if proteina is None:
            raise NaoEncontrado("Proteína não encontrada.")
        if not proteina.ativo:
            raise RegraViolada("A proteína precisa estar ativa para ser usada em prato.")
        return proteina

    async def _buscar(self, prato_id: int) -> Prato:
        prato = await self._pratos.buscar_por_id(prato_id)
        if prato is None:
            raise NaoEncontrado("Prato não encontrado.")
        return prato

    async def _exigir_nome_livre(self, nome: str, ignorando: int | None) -> None:
        existente = await self._pratos.buscar_por_nome(nome)
        if existente is not None and existente.id != ignorando:
            mensagem = MENSAGEM_PRATO_DESATIVADO if not existente.ativo else MENSAGEM_PRATO_REPETIDO
            raise Conflito(mensagem)

    async def _leitura(self, prato: Prato, proteina_nome: str | None = None) -> PratoLeitura:
        if proteina_nome is None:
            proteina = await self._proteinas.buscar_por_id(prato.proteina_id)
            proteina_nome = proteina.nome if proteina else ""
        itens = await self._pratos.itens_ativos_do_prato(prato.id)
        return PratoLeitura(
            id=prato.id,
            nome=prato.nome,
            proteina_id=prato.proteina_id,
            proteina_nome=proteina_nome,
            gramas_por_porcao=prato.gramas_por_porcao,
            ativo=prato.ativo,
            itens_ativos=len(itens),
        )
