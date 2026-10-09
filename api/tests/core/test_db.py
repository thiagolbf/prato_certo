"""Dependência de sessão da requisição: commit ao fim quando não há exceção, rollback quando há.

Testa `obter_sessao` real, contra o engine de teste, com linhas gravadas de verdade: uma
sessão de outra conexão confere o que ficou no banco. Cada teste apaga a própria linha.
"""

import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Configuracao
from app.core.db import SessaoDaRequisicao, criar_fabrica_sessoes, obter_sessao
from app.core.estabelecimento import estabelecimento_atual
from app.identidade.modelos import Perfil, Usuario
from app.main import MENSAGEM_ERRO_INTERNO, criar_app


def _requisicao(engine: AsyncEngine) -> SimpleNamespace:
    fabrica = criar_fabrica_sessoes(engine)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(fabrica_sessoes=fabrica)))


async def _gravar_usuario(sessao, login: str) -> None:
    sessao.add(
        Usuario.criar(
            estabelecimento_id=await estabelecimento_atual(sessao),
            nome="Teste",
            login=login,
            senha_hash="hash-de-teste",
            perfil=Perfil.OPERADOR,
        )
    )


async def _existe(engine: AsyncEngine, login: str) -> bool:
    async with criar_fabrica_sessoes(engine)() as outra:
        return await outra.scalar(select(Usuario.id).where(Usuario.login == login)) is not None


async def _apagar(engine: AsyncEngine, login: str) -> None:
    async with criar_fabrica_sessoes(engine)() as outra:
        await outra.execute(delete(Usuario).where(Usuario.login == login))
        await outra.commit()


async def test_obter_sessao_commita_ao_fim_da_requisicao(engine: AsyncEngine) -> None:
    login = f"commit-{uuid.uuid4().hex[:8]}"
    gerador = obter_sessao(_requisicao(engine))
    try:
        sessao = await anext(gerador)
        await _gravar_usuario(sessao, login)

        with pytest.raises(StopAsyncIteration):
            await anext(gerador)

        assert await _existe(engine, login)
    finally:
        await _apagar(engine, login)


async def test_obter_sessao_desfaz_a_requisicao_que_falha(engine: AsyncEngine) -> None:
    login = f"rollback-{uuid.uuid4().hex[:8]}"
    gerador = obter_sessao(_requisicao(engine))
    try:
        sessao = await anext(gerador)
        await _gravar_usuario(sessao, login)

        with pytest.raises(RuntimeError):
            await gerador.athrow(RuntimeError("falha na rota"))

        assert not await _existe(engine, login)
    finally:
        await _apagar(engine, login)


class EspiaDeEnvio:
    """Registra, no instante em que o corpo da resposta sai, se a linha já está no banco."""

    def __init__(self, app, verificar) -> None:
        self.app = app
        self.verificar = verificar
        self.resultados: list[bool] = []

    async def __call__(self, scope, receive, send) -> None:
        async def espiar(mensagem) -> None:
            if mensagem["type"] == "http.response.body" and not mensagem.get("more_body", False):
                self.resultados.append(await self.verificar())
            await send(mensagem)

        await self.app(scope, receive, espiar)


async def test_commit_acontece_antes_do_envio_da_resposta(
    configuracao: Configuracao, engine: AsyncEngine
) -> None:
    login = f"envio-{uuid.uuid4().hex[:8]}"
    app = criar_app(configuracao)

    @app.post("/teste/gravar", include_in_schema=False)
    async def gravar(sessao: SessaoDaRequisicao) -> dict[str, bool]:
        await _gravar_usuario(sessao, login)
        return {"ok": True}

    espiao = EspiaDeEnvio(app, lambda: _existe(engine, login))
    try:
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=espiao), base_url="http://teste") as cliente,
        ):
            resposta = await cliente.post("/teste/gravar")

        assert resposta.status_code == 200
        assert espiao.resultados == [True]
    finally:
        await _apagar(engine, login)


async def test_falha_de_commit_vira_erro_e_nao_sucesso(configuracao: Configuracao) -> None:
    app = criar_app(configuracao)

    @app.post("/teste/gravar-invalido", include_in_schema=False)
    async def gravar_invalido(sessao: SessaoDaRequisicao) -> dict[str, bool]:
        # Estabelecimento que não existe: a violação de chave estrangeira aparece no commit.
        sessao.add(
            Usuario.criar(
                estabelecimento_id=987654321,
                nome="Sem estabelecimento",
                login=f"invalido-{uuid.uuid4().hex[:8]}",
                senha_hash="hash-de-teste",
                perfil=Perfil.OPERADOR,
            )
        )
        return {"ok": True}

    # O handler de erro interno envia o 500 e depois relança para o log do servidor; o transporte
    # de teste não deve relançar, para o teste ver a resposta.
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://teste"
        ) as cliente,
    ):
        resposta = await cliente.post("/teste/gravar-invalido")

    assert resposta.status_code == 500
    assert resposta.json() == {"detail": MENSAGEM_ERRO_INTERNO}
