"""Serviço de vendas: registro idempotente com o instante do servidor (RN-17, RN-18, RN-19).

Só orquestra. O item vem do serviço do cardápio, pelo objeto de leitura `ItemVendavel`, e a
regra de quantidade, snapshot e totais fica em `Venda.registrar`.
"""

from app.catalogo.servico_cardapio import ServicoCardapio
from app.core.excecoes import NaoEncontrado
from app.core.relogio import Relogio
from app.core.tempo import DiaOperacional
from app.vendas.leitura import ResultadoRegistro, VendaLeitura
from app.vendas.modelos import Venda
from app.vendas.repositorio import RepositorioVendas


def _leitura(venda: Venda) -> VendaLeitura:
    return VendaLeitura(
        id=venda.id,
        prato_nome=venda.prato_nome,
        proteina_nome=venda.proteina_nome,
        formato=venda.formato,
        quantidade=venda.quantidade,
        preco_unitario=venda.preco_unitario,
        valor_total=venda.valor_total,
        proteina_total_g=venda.proteina_total_g,
        registrada_em=venda.registrada_em,
        cancelada_em=venda.cancelada_em,
    )


class ServicoVendas:
    def __init__(
        self,
        repositorio: RepositorioVendas,
        cardapio: ServicoCardapio,
        relogio: Relogio,
    ) -> None:
        self._repositorio = repositorio
        self._cardapio = cardapio
        self._relogio = relogio

    async def registrar(
        self, item_id: int, quantidade: int, chave: str, usuario_id: int
    ) -> ResultadoRegistro:
        # Reenvio da mesma chave devolve a venda original, mesmo que o cardápio tenha mudado
        # desde a primeira tentativa (RN-18): por isso a chave é olhada antes do item.
        existente = await self._repositorio.buscar_por_chave(chave)
        if existente is not None:
            return ResultadoRegistro(venda=_leitura(existente), criada=False)

        # O instante é do servidor (RN-17, ADR-005); o dia operacional sai dele, e não do
        # aparelho.
        agora = self._relogio.agora()
        hoje = DiaOperacional.do_instante(agora).data
        item = await self._cardapio.item_vendavel(item_id, hoje)

        venda = Venda.registrar(
            estabelecimento_id=self._repositorio.estabelecimento_id,
            item=item,
            quantidade=quantidade,
            usuario_id=usuario_id,
            chave=chave,
            agora=agora,
        )
        id_gravado = await self._repositorio.inserir_se_nova(venda)
        if id_gravado is None:
            # Outra requisição com a mesma chave gravou antes: devolve a dela, sem criar outra.
            original = await self._repositorio.buscar_por_chave(chave)
            return ResultadoRegistro(venda=_leitura(original), criada=False)

        gravada = await self._repositorio.buscar_por_id(id_gravado)
        return ResultadoRegistro(venda=_leitura(gravada), criada=True)

    async def cancelar(self, venda_id: int, por: int, motivo: str) -> VendaLeitura:
        """Cancela logicamente, sem olhar a data da venda (RN-22). A trava `FOR UPDATE` faz o
        segundo cancelamento simultâneo ver a venda já cancelada e recusar (RN-25)."""
        venda = await self._repositorio.buscar_por_id_para_cancelar(venda_id)
        if venda is None:
            raise NaoEncontrado("Venda não encontrada.")
        venda.cancelar(por=por, motivo=motivo, agora=self._relogio.agora())
        await self._repositorio.persistir()
        return _leitura(venda)
