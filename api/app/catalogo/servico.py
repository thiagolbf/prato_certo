"""Serviço de proteínas: nome único, desativação protegida e reativação (RN-01, RN-49, RN-58).

Só orquestra: a regra de nome e de desativação está na entidade e no repositório. A checagem
de dependentes e a desativação acontecem na mesma transação, com a proteína travada.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.catalogo.repositorio import RepositorioItens, RepositorioPratos, RepositorioProteinas
from app.core.excecoes import Conflito, NaoEncontrado, RegraViolada
from app.core.valores import Dinheiro

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
        # Trava o prato: um item criado em paralelo espera esta transação (RN-58).
        prato = await self._pratos.buscar_por_id_para_atualizar(prato_id)
        if prato is None:
            raise NaoEncontrado("Prato não encontrado.")
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


MENSAGEM_ITEM_REPETIDO = "Já existe um item desse prato neste formato."
MENSAGEM_ITEM_DESATIVADO = (
    "Já existe um item desativado desse prato neste formato. Reative-o em vez de criar outro."
)


@dataclass(frozen=True)
class ItemLeitura:
    id: int
    prato_id: int
    prato_nome: str
    formato: Formato
    gramas_por_porcao: int
    preco: Decimal
    ativo: bool

    @property
    def nome(self) -> str:
        return f"{self.prato_nome} - {ROTULO_FORMATO[self.formato]}"


class ServicoItens:
    """Itens de cardápio: prato × formato com preço próprio (RN-03, RN-59)."""

    def __init__(self, itens: RepositorioItens, pratos: RepositorioPratos) -> None:
        self._itens = itens
        self._pratos = pratos

    async def listar(self, incluir_desativados: bool) -> list[ItemLeitura]:
        return [
            ItemLeitura(
                id=item.id,
                prato_id=item.prato_id,
                prato_nome=prato_nome,
                formato=item.formato,
                gramas_por_porcao=gramas,
                preco=item.preco,
                ativo=item.ativo,
            )
            for item, prato_nome, gramas in await self._itens.listar(incluir_desativados)
        ]

    async def criar(self, prato_id: int, formato: Formato, preco: Dinheiro) -> ItemLeitura:
        # Trava o prato: a criação de item e a desativação do prato se serializam (RN-58).
        prato = await self._pratos.buscar_por_id_para_atualizar(prato_id)
        if prato is None:
            raise NaoEncontrado("Prato não encontrado.")
        if not prato.ativo:
            raise RegraViolada("O prato precisa estar ativo para ter itens de cardápio.")
        existente = await self._itens.buscar_por_prato_e_formato(prato.id, formato)
        if existente is not None:
            mensagem = MENSAGEM_ITEM_REPETIDO if existente.ativo else MENSAGEM_ITEM_DESATIVADO
            raise Conflito(mensagem)
        try:
            item = ItemCardapio.criar(
                estabelecimento_id=prato.estabelecimento_id,
                prato_id=prato.id,
                formato=formato,
                preco=preco,
            )
        except ValueError as erro:
            raise RegraViolada(str(erro)) from erro
        self._itens.adicionar(item)
        try:
            await self._itens.persistir()
        except IntegrityError as erro:
            # Corrida: outro item do mesmo par entrou entre a checagem e o insert.
            raise Conflito(MENSAGEM_ITEM_REPETIDO) from erro
        logger.info("item criado", extra={"item_id": item.id})
        return await self._leitura(item, prato)

    async def alterar_preco(self, item_id: int, preco: Dinheiro) -> ItemLeitura:
        """Só o preço muda: prato e formato são fixos depois de criados (RN-05, ADR-004)."""
        item = await self._buscar(item_id)
        try:
            item.alterar_preco(preco)
        except ValueError as erro:
            raise RegraViolada(str(erro)) from erro
        return await self._leitura(item)

    async def desativar(self, item_id: int) -> ItemLeitura:
        item = await self._buscar(item_id)
        item.desativar()
        logger.info("item desativado", extra={"item_id": item.id})
        return await self._leitura(item)

    async def reativar(self, item_id: int) -> ItemLeitura:
        item = await self._buscar(item_id)
        prato = await self._pratos.buscar_por_id(item.prato_id)
        if prato is None or not prato.ativo:
            # Item de prato desativado seria vendável sem prato (RN-58).
            raise RegraViolada("O prato do item está desativado. Reative-o antes.")
        item.reativar()
        return await self._leitura(item, prato)

    async def _buscar(self, item_id: int) -> ItemCardapio:
        item = await self._itens.buscar_por_id(item_id)
        if item is None:
            raise NaoEncontrado("Item não encontrado.")
        return item

    async def _leitura(self, item: ItemCardapio, prato: Prato | None = None) -> ItemLeitura:
        if prato is None:
            prato = await self._pratos.buscar_por_id(item.prato_id)
        return ItemLeitura(
            id=item.id,
            prato_id=item.prato_id,
            prato_nome=prato.nome if prato else "",
            formato=item.formato,
            gramas_por_porcao=prato.gramas_por_porcao if prato else 0,
            preco=item.preco,
            ativo=item.ativo,
        )
