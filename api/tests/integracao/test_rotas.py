"""Inventário das rotas: nenhum GET altera estado e nenhuma rota PUT existe (ADR-006, RN-42).

O teste percorre todas as rotas da aplicação, chama cada GET com dados reais semeados e compara a
contagem de linhas de todas as tabelas antes e depois. A exceção é a tabela `sessao`: a renovação
por uso (RN-36) grava a nova expiração em qualquer requisição autenticada, por desenho, e não é
alteração de dado de negócio.
"""

import re

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.modelo_base import Base
from app.identidade.modelos import Perfil
from tests.integracao.test_imutabilidade import (
    HOJE,
    RelogioFixo,
    _cardapio_herdado_de_ontem,
    _entrar_como,
    _item,
    _meio_dia,
    _usuario,
    _vender,
)

TABELAS_DA_RENOVACAO = {"sessao"}


async def _contagens(sessao: AsyncSession) -> dict[str, int]:
    contagens: dict[str, int] = {}
    for tabela in Base.metadata.sorted_tables:
        if tabela.name in TABELAS_DA_RENOVACAO:
            continue
        contagens[tabela.name] = await sessao.scalar(select(func.count()).select_from(tabela)) or 0
    return contagens


def _rotas(app: FastAPI) -> list:
    """Rotas da aplicação, achatando os roteadores incluídos (`include_router` os encapsula)."""
    achatadas = []
    for rota in app.routes:
        if hasattr(rota, "original_router"):
            achatadas.extend(rota.original_router.routes)
        else:
            achatadas.append(rota)
    return achatadas


def test_nenhuma_rota_put_existe(app: FastAPI) -> None:
    metodos = {m for rota in _rotas(app) for m in getattr(rota, "methods", set())}
    assert "PUT" not in metodos


async def test_nenhuma_rota_get_altera_estado(
    app: FastAPI, cliente: AsyncClient, sessao: AsyncSession
) -> None:
    feijoada = await _item(sessao, "Feijoada")
    await _cardapio_herdado_de_ontem(sessao, feijoada)
    operador = await _usuario(sessao, "joao", Perfil.OPERADOR)
    admin = await _usuario(sessao, "thiago", Perfil.ADMIN)
    await _entrar_como(app, cliente, sessao, operador, RelogioFixo(_meio_dia(HOJE)))
    await _vender(cliente, feijoada, 2, "inventario-1")
    await _entrar_como(app, cliente, sessao, admin, RelogioFixo(_meio_dia(HOJE)))

    antes = await _contagens(sessao)
    consultados: list[str] = []
    for rota in _rotas(app):
        if "GET" not in getattr(rota, "methods", set()):
            continue
        caminho = re.sub(r"\{[^}]+\}", "1", rota.path)
        await cliente.get(caminho, params={"data": HOJE.isoformat(), "mes": "2026-10"})
        consultados.append(caminho)
    depois = await _contagens(sessao)

    assert "/api/fechamento/dia" in consultados
    assert "/api/vendas" in consultados
    assert antes == depois, {t: (antes[t], depois[t]) for t in antes if antes[t] != depois[t]}
