"""Lista de vendas da data para o ADMIN: GET /api/vendas?data= (RN-27, RN-28, RN-34, RN-51).

O dia 08/10 é o dia operacional do relógio fixo (12:00 UTC é 09:00 em São Paulo). A lista da
data não depende do relógio; o relógio só serve para autenticar cada papel.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import CardapioData, Formato, ItemCardapio, Prato, Proteina
from app.core.estabelecimento import estabelecimento_atual
from app.core.relogio import obter_relogio
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

REGISTRO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
HOJE = date(2026, 10, 8)
SENHA = "senha-do-teste"
ROTA_VENDAS = "/api/vendas"
ROTA_DA_DATA = f"{ROTA_VENDAS}?data=2026-10-08"
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)


class RelogioFixo:
    def __init__(self, instante: datetime = REGISTRO) -> None:
        self._instante = instante

    def agora(self) -> datetime:
        return self._instante


async def _usuario(sessao: AsyncSession, login: str, nome: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=nome,
        login=login,
        senha_hash=await gerar_hash(SENHA),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _entrar_como(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, usuario: Usuario
) -> None:
    relogio = RelogioFixo()
    app.dependency_overrides[obter_relogio] = lambda: relogio
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        relogio,
    )
    cliente.cookies.set(NOME_COOKIE_SESSAO, await servico.abrir(usuario))


async def _item(sessao: AsyncSession, nome_prato: str) -> ItemCardapio:
    estabelecimento_id = await estabelecimento_atual(sessao)
    proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Proteína {nome_prato}")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=estabelecimento_id,
        nome=nome_prato,
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    sessao.add(prato)
    await sessao.flush()
    item = ItemCardapio.criar(
        estabelecimento_id=estabelecimento_id,
        prato_id=prato.id,
        formato=Formato.PF,
        preco=Dinheiro("18.00"),
    )
    sessao.add(item)
    await sessao.flush()
    return item


async def _cardapio_de_hoje(sessao: AsyncSession, *itens: ItemCardapio) -> None:
    sessao.add(
        CardapioData.definir(
            estabelecimento_id=await estabelecimento_atual(sessao),
            data=HOJE,
            itens=list(itens),
            hoje=HOJE,
        )
    )
    await sessao.flush()


async def _registrar(
    app: FastAPI,
    cliente: AsyncClient,
    sessao: AsyncSession,
    operador: Usuario,
    item: ItemCardapio,
    quantidade: int,
    prefixo: str,
) -> list[int]:
    await _entrar_como(app, cliente, sessao, operador)
    ids = []
    for indice in range(quantidade):
        resposta = await cliente.post(
            ROTA_VENDAS,
            json={"item_id": item.id, "quantidade": 1, "chave_idempotencia": f"{prefixo}-{indice}"},
        )
        assert resposta.status_code == 201
        ids.append(resposta.json()["id"])
    return ids


async def test_CA_50_admin_ve_todas_as_vendas_da_data(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    joao = await _usuario(sessao, "joao", "João", Perfil.OPERADOR)
    maria = await _usuario(sessao, "maria", "Maria", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    vendas_joao = await _registrar(app, cliente, sessao, joao, item, 5, "joao")
    await _registrar(app, cliente, sessao, maria, item, 3, "maria")
    await _entrar_como(app, cliente, sessao, admin)
    cancelamento = await cliente.post(
        f"{ROTA_VENDAS}/{vendas_joao[0]}/cancelar", json={"motivo": "lançado em dobro"}
    )
    assert cancelamento.status_code == 200

    resposta = await cliente.get(ROTA_DA_DATA)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["vendas"]) == 8
    # Cada venda traz item, formato, quantidade, preço, valor, autor e horário (RN-51).
    for venda in corpo["vendas"]:
        assert venda["prato_nome"] == "Frango grelhado"
        assert venda["formato"] == "PF"
        assert venda["quantidade"] == 1
        assert venda["valor_total"] == "18.00"
        assert venda["horario"].startswith("2026-10-08T09:")
        assert venda["horario"].endswith("-03:00")
    cancelada = next(venda for venda in corpo["vendas"] if venda["id"] == vendas_joao[0])
    assert cancelada["cancelada"] is True
    assert cancelada["cancelada_por"] == "Admin"
    assert cancelada["motivo_cancelamento"] == "lançado em dobro"
    assert cancelada["cancelada_em"] is not None
    assert cancelada["autor"] == "João"
    assert cancelada["preco_unitario"] == "18.00"
    # Os totais excluem a cancelada: 7 unidades de 18,00 (RN-28).
    assert corpo["total_unidades"] == 7
    assert Decimal(corpo["total_valor"]) == Decimal("126.00")


async def test_CA_27_usuario_desativado_preserva_autoria(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    joao = await _usuario(sessao, "joao", "João", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    vendas_joao = await _registrar(app, cliente, sessao, joao, item, 4, "desativado")
    await _entrar_como(app, cliente, sessao, admin)

    desativacao = await cliente.post(f"/api/usuarios/{joao.id}/desativar")
    assert desativacao.status_code == 200
    login = await cliente.post("/api/auth/login", json={"login": "joao", "senha": SENHA})
    assert login.status_code == 401
    lista = await cliente.get(ROTA_DA_DATA)

    # Não consegue entrar, e as vendas continuam dele no histórico (RN-34).
    atribuidas = [venda for venda in lista.json()["vendas"] if venda["id"] in vendas_joao]
    assert len(atribuidas) == 4
    assert {venda["autor"] for venda in atribuidas} == {"João"}


async def test_CA_53_operador_reativado_volta_a_autenticar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    joao = await _usuario(sessao, "joao", "João", Perfil.OPERADOR)
    admin = await _usuario(sessao, "admin", "Admin", Perfil.ADMIN)
    item = await _item(sessao, "Frango grelhado")
    await _cardapio_de_hoje(sessao, item)
    vendas_joao = await _registrar(app, cliente, sessao, joao, item, 2, "reativado")
    await _entrar_como(app, cliente, sessao, admin)
    await cliente.post(f"/api/usuarios/{joao.id}/desativar")
    await _entrar_como(app, cliente, sessao, admin)

    reativacao = await cliente.post(f"/api/usuarios/{joao.id}/reativar")
    assert reativacao.status_code == 200
    login = await cliente.post("/api/auth/login", json={"login": "joao", "senha": SENHA})
    assert login.status_code == 200
    await _entrar_como(app, cliente, sessao, admin)
    lista = await cliente.get(ROTA_DA_DATA)

    # As vendas anteriores continuam atribuídas a ele (RN-34).
    atribuidas = [venda for venda in lista.json()["vendas"] if venda["id"] in vendas_joao]
    assert {venda["autor"] for venda in atribuidas} == {"João"}


async def test_operador_nao_ve_a_lista_da_data(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    operador = await _usuario(sessao, "joao", "João", Perfil.OPERADOR)
    await _entrar_como(app, cliente, sessao, operador)

    resposta = await cliente.get(ROTA_DA_DATA)

    assert resposta.status_code == 403
