"""Serviço do cardápio vigente e da leitura de item vendável (RN-08, RN-09, RN-11, RN-19, RN-50).

Só orquestra: a herança é `CardapioData.herdar_de`, na entidade. Nada é gravado aqui: abrir a
tela de registro nunca altera estado (RN-08, RN-42).
"""

from datetime import date

from sqlalchemy.exc import IntegrityError

from app.catalogo.leitura import (
    CardapioVigente,
    ItemForaDoCardapio,
    ItemVendavel,
    TipoCardapio,
)
from app.catalogo.modelos import CardapioData
from app.catalogo.repositorio import RepositorioCardapios
from app.core.excecoes import Conflito, NaoEncontrado

MENSAGEM_CARDAPIO_CONCORRENTE = (
    "Este cardápio foi alterado por outra pessoa. Atualize e tente de novo."
)


class ServicoCardapio:
    def __init__(self, repositorio: RepositorioCardapios) -> None:
        self._repositorio = repositorio

    async def definir(self, data: date, item_ids: list[int], hoje: date) -> CardapioVigente:
        """Grava o cardápio próprio da data, criando ou trocando os itens (RN-10, RN-50, RN-57).

        Confirmar o herdado é mandar os mesmos itens. As regras estão em `CardapioData`.
        """
        pedidos = list(dict.fromkeys(item_ids))
        encontrados = await self._repositorio.buscar_itens(pedidos)
        if len(encontrados) != len(pedidos):
            raise NaoEncontrado("Item não encontrado.")

        cardapio = await self._repositorio.buscar_proprio(data)
        if cardapio is None:
            cardapio = CardapioData.definir(
                estabelecimento_id=self._repositorio.estabelecimento_id,
                data=data,
                itens=list(encontrados),
                hoje=hoje,
            )
            self._repositorio.adicionar(cardapio)
        else:
            cardapio.substituir_itens(list(encontrados), hoje=hoje)
        try:
            await self._repositorio.persistir()
        except IntegrityError as erro:
            # Corrida: outra gravação da mesma data entrou antes; o índice único recusa.
            raise Conflito(MENSAGEM_CARDAPIO_CONCORRENTE) from erro
        return await self._montar(data, TipoCardapio.PROPRIO, None, cardapio)

    async def cardapio_vigente(self, data: date) -> CardapioVigente:
        """Próprio da data; sem ele, o herdado do anterior mais recente; sem nenhum, vazio."""
        proprio = await self._repositorio.buscar_proprio(data)
        if proprio is not None:
            return await self._montar(data, TipoCardapio.PROPRIO, None, proprio)

        anterior = await self._repositorio.mais_recente_anterior(data)
        if anterior is None:
            return CardapioVigente(data=data, tipo=TipoCardapio.VAZIO, data_origem=None, itens=())

        herdado = CardapioData.herdar_de(anterior, data)
        return await self._montar(data, TipoCardapio.HERDADO, anterior.data, herdado)

    async def item_vendavel(self, item_id: int, data: date) -> ItemVendavel:
        """O item, se está no vigente da data. É o caminho de `vendas` ao catálogo (RN-19)."""
        vigente = await self.cardapio_vigente(data)
        for item in vigente.itens:
            if item.item_id == item_id:
                return item
        raise ItemForaDoCardapio("Este item não está no cardápio de hoje.")

    async def _montar(
        self,
        data: date,
        tipo: TipoCardapio,
        data_origem: date | None,
        cardapio: CardapioData,
    ) -> CardapioVigente:
        linhas = await self._repositorio.itens_vendaveis([item.id for item in cardapio.itens])
        itens = tuple(
            ItemVendavel(
                item_id=item.id,
                nome_prato=nome_prato,
                nome_proteina=nome_proteina,
                formato=item.formato,
                preco=item.preco,
                gramas_por_porcao=gramas,
            )
            for item, nome_prato, nome_proteina, gramas in linhas
        )
        return CardapioVigente(data=data, tipo=tipo, data_origem=data_origem, itens=itens)
