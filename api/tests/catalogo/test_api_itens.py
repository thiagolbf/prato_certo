"""Itens de cardápio pela API: prato × formato com preço próprio (RN-03, RN-05, RN-49, RN-59).

Todas as rotas são de ADMIN. A edição só altera o preço: prato e formato não mudam. O cookie
volta à mão por causa do `Secure`.
"""

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalogo.modelos import Formato, ItemCardapio, Prato, Proteina
from app.catalogo.repositorio import RepositorioItens, RepositorioPratos, RepositorioProteinas
from app.catalogo.servico import ServicoItens, ServicoPratos
from app.core.db import criar_fabrica_sessoes
from app.core.estabelecimento import estabelecimento_atual
from app.core.excecoes import Conflito, RegraViolada
from app.core.relogio import obter_relogio
from app.core.valores import Dinheiro
from app.identidade.dependencias import NOME_COOKIE_SESSAO
from app.identidade.modelos import Perfil, PoliticaDeSessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

INICIO = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
POLITICA_SESSAO = PoliticaDeSessao(
    inatividade_admin=timedelta(minutes=30), inatividade_operador=timedelta(hours=12)
)
ROTA = "/api/itens"


class RelogioFixo:
    def agora(self) -> datetime:
        return INICIO


async def _usuario(sessao: AsyncSession, login: str, perfil: Perfil) -> Usuario:
    usuario = Usuario.criar(
        estabelecimento_id=await estabelecimento_atual(sessao),
        nome=login.capitalize(),
        login=login,
        senha_hash=await gerar_hash("senha-do-teste"),
        perfil=perfil,
    )
    sessao.add(usuario)
    await sessao.flush()
    return usuario


async def _entrar_como(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession, usuario: Usuario
) -> None:
    app.dependency_overrides[obter_relogio] = lambda: RelogioFixo()
    estabelecimento_id = await estabelecimento_atual(sessao)
    servico = ServicoSessao(
        RepositorioSessoes(sessao, estabelecimento_id),
        RepositorioUsuarios(sessao, estabelecimento_id),
        POLITICA_SESSAO,
        RelogioFixo(),
    )
    cliente.cookies.set(NOME_COOKIE_SESSAO, await servico.abrir(usuario))


async def _admin_logado(app: FastAPI, cliente: AsyncClient, sessao: AsyncSession) -> Usuario:
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, admin)
    return admin


async def _prato(sessao: AsyncSession, nome: str = "Frango grelhado", ativo: bool = True) -> Prato:
    proteina = Proteina.criar(estabelecimento_id=await estabelecimento_atual(sessao), nome="Frango")
    sessao.add(proteina)
    await sessao.flush()
    prato = Prato.criar(
        estabelecimento_id=proteina.estabelecimento_id,
        nome=nome,
        proteina_id=proteina.id,
        gramas_por_porcao=150,
    )
    if not ativo:
        prato.desativar()
    sessao.add(prato)
    await sessao.flush()
    return prato


async def _item(
    sessao: AsyncSession, prato: Prato, formato: Formato, preco: str = "18.00"
) -> ItemCardapio:
    item = ItemCardapio.criar(
        estabelecimento_id=prato.estabelecimento_id,
        prato_id=prato.id,
        formato=formato,
        preco=Dinheiro(preco),
    )
    sessao.add(item)
    await sessao.flush()
    return item


async def test_CA_30_mesmo_prato_em_dois_formatos_tem_precos_independentes(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao)

    pf = await cliente.post(ROTA, json={"prato_id": prato.id, "formato": "PF", "preco": "18.00"})
    marmita = await cliente.post(
        ROTA, json={"prato_id": prato.id, "formato": "MARMITA", "preco": "22.00"}
    )

    assert pf.status_code == 201
    assert marmita.status_code == 201
    assert pf.json()["preco"] == "18.00"
    assert marmita.json()["preco"] == "22.00"
    assert pf.json()["gramas_por_porcao"] == marmita.json()["gramas_por_porcao"] == 150
    assert pf.json()["nome"] == "Frango grelhado - PF"


async def test_CA_64_segundo_item_do_mesmo_prato_e_formato_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao)
    await _item(sessao, prato, Formato.PF)

    resposta = await cliente.post(
        ROTA, json={"prato_id": prato.id, "formato": "PF", "preco": "19.00"}
    )

    assert resposta.status_code == 409


async def test_item_desativado_no_mesmo_par_indica_reativar(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao)
    item = await _item(sessao, prato, Formato.PF)
    item.desativar()
    await sessao.flush()

    resposta = await cliente.post(
        ROTA, json={"prato_id": prato.id, "formato": "PF", "preco": "19.00"}
    )

    assert resposta.status_code == 409
    assert "reativ" in resposta.json()["detail"].lower()


async def test_edicao_so_altera_preco(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao)
    item = await _item(sessao, prato, Formato.PF, preco="18.00")

    trocou_prato = await cliente.post(
        f"{ROTA}/{item.id}/preco", json={"preco": "20.00", "prato_id": 99}
    )
    assert trocou_prato.status_code == 422

    trocou_formato = await cliente.post(
        f"{ROTA}/{item.id}/preco", json={"preco": "20.00", "formato": "MARMITA"}
    )
    assert trocou_formato.status_code == 422

    ok = await cliente.post(f"{ROTA}/{item.id}/preco", json={"preco": "20.00"})
    assert ok.status_code == 200
    assert ok.json()["preco"] == "20.00"
    await sessao.refresh(item)
    assert item.prato_id == prato.id
    assert item.formato is Formato.PF


async def test_reativar_item(app: FastAPI, cliente: AsyncClient, sessao: AsyncSession) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao)
    item = await _item(sessao, prato, Formato.MARMITA)

    desativado = await cliente.post(f"{ROTA}/{item.id}/desativar")
    assert desativado.status_code == 200
    assert desativado.json()["ativo"] is False

    reativado = await cliente.post(f"{ROTA}/{item.id}/reativar")
    assert reativado.status_code == 200
    assert reativado.json()["ativo"] is True
    assert reativado.json()["preco"] == "18.00"


async def test_reativar_item_de_prato_desativado_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao, ativo=False)
    item = await _item(sessao, prato, Formato.PF)
    item.desativar()
    await sessao.flush()

    resposta = await cliente.post(f"{ROTA}/{item.id}/reativar")

    assert resposta.status_code == 422


async def test_item_de_prato_desativado_nao_e_criado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao, ativo=False)

    resposta = await cliente.post(
        ROTA, json={"prato_id": prato.id, "formato": "PF", "preco": "18.00"}
    )

    assert resposta.status_code == 422


async def test_preco_zero_e_recusado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    await _admin_logado(app, cliente, sessao)
    prato = await _prato(sessao)

    resposta = await cliente.post(ROTA, json={"prato_id": prato.id, "formato": "PF", "preco": "0"})

    assert resposta.status_code == 422


async def test_criacao_de_item_e_desativacao_do_prato_se_serializam(configuracao, engine) -> None:
    """Criar item e desativar o prato em paralelo não deixam item ativo de prato desativado (RN-58).

    Dados gravados de verdade (duas sessões em paralelo), com limpeza no fim.
    """
    fabrica = criar_fabrica_sessoes(engine)
    sufixo = uuid.uuid4().hex[:8]
    async with fabrica() as sessao, sessao.begin():
        estabelecimento_id = await estabelecimento_atual(sessao)
        proteina = Proteina.criar(estabelecimento_id=estabelecimento_id, nome=f"Frango {sufixo}")
        sessao.add(proteina)
        await sessao.flush()
        prato = Prato.criar(
            estabelecimento_id=estabelecimento_id,
            nome=f"Prato {sufixo}",
            proteina_id=proteina.id,
            gramas_por_porcao=150,
        )
        sessao.add(prato)
        await sessao.flush()
        prato_id, proteina_id = prato.id, proteina.id

    async def criar_item() -> None:
        async with fabrica() as sessao, sessao.begin():
            servico = ServicoItens(
                RepositorioItens(sessao, estabelecimento_id),
                RepositorioPratos(sessao, estabelecimento_id),
            )
            # Se o prato já estiver desativado, a criação é recusada.
            with contextlib.suppress(RegraViolada):
                await servico.criar(prato_id, Formato.PF, Dinheiro("18.00"))

    async def desativar_prato() -> None:
        async with fabrica() as sessao, sessao.begin():
            servico = ServicoPratos(
                RepositorioPratos(sessao, estabelecimento_id),
                RepositorioProteinas(sessao, estabelecimento_id),
            )
            # Se o item já existir, a desativação é recusada.
            with contextlib.suppress(Conflito):
                await servico.desativar(prato_id)

    try:
        await asyncio.gather(criar_item(), desativar_prato())

        async with fabrica() as sessao:
            prato_final = await sessao.get(Prato, prato_id)
            itens_ativos = await sessao.scalar(
                select(func.count(ItemCardapio.id)).where(
                    ItemCardapio.prato_id == prato_id, ItemCardapio.ativo.is_(True)
                )
            )
        assert not (prato_final.ativo is False and itens_ativos > 0)
    finally:
        async with fabrica() as sessao, sessao.begin():
            await sessao.execute(delete(ItemCardapio).where(ItemCardapio.prato_id == prato_id))
            await sessao.execute(delete(Prato).where(Prato.id == prato_id))
            await sessao.execute(delete(Proteina).where(Proteina.id == proteina_id))
