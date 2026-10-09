"""Ponto de entrada da API: monta a aplicação, as rotas transversais e o tratamento de erros."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Configuracao, obter_configuracao
from app.core.db import SessaoDaRequisicao, criar_engine, criar_fabrica_sessoes
from app.core.excecoes import (
    Conflito,
    ErroDeDominio,
    NaoAutenticado,
    NaoEncontrado,
    RegraViolada,
    SemPermissao,
)
from app.core.log import configurar_log
from app.core.seguranca import CABECALHOS_DE_SEGURANCA, instalar_seguranca
from app.identidade.router import router as router_identidade
from app.identidade.router import router_usuarios

logger = logging.getLogger("app.erros")

MENSAGEM_ERRO_INTERNO = "Erro interno. Tente novamente."
STATUS_POR_ERRO: dict[type[ErroDeDominio], int] = {
    NaoEncontrado: 404,
    Conflito: 409,
    RegraViolada: 422,
    NaoAutenticado: 401,
    SemPermissao: 403,
}


def _erro_interno(request: Request, erro: Exception) -> JSONResponse:
    """Detalhe só no log do servidor; ao cliente, mensagem neutra (RN-48)."""
    logger.error(
        "erro inesperado",
        exc_info=erro,
        extra={"metodo": request.method, "caminho": request.url.path},
    )
    # Esta resposta sai pelo ServerErrorMiddleware, por fora dos middlewares de segurança.
    return JSONResponse(
        {"detail": MENSAGEM_ERRO_INTERNO}, status_code=500, headers=CABECALHOS_DE_SEGURANCA
    )


async def _tratar_erro_de_dominio(request: Request, erro: ErroDeDominio) -> JSONResponse:
    """O único ponto que traduz exceção de domínio em HTTP (ADR-009, item 7)."""
    for classe in type(erro).__mro__:
        if classe in STATUS_POR_ERRO:
            return JSONResponse({"detail": erro.mensagem}, status_code=STATUS_POR_ERRO[classe])
    return _erro_interno(request, erro)


async def _tratar_erro_de_validacao(request: Request, erro: RequestValidationError) -> JSONResponse:
    """O 422 padrão do FastAPI ecoa o corpo recebido (`input`); aqui só onde e o quê."""
    detalhes = [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in erro.errors()
    ]
    return JSONResponse({"detail": detalhes}, status_code=422)


async def _tratar_erro_inesperado(request: Request, erro: Exception) -> JSONResponse:
    return _erro_interno(request, erro)


def _instalar_documentacao(app: FastAPI) -> None:
    """`/docs`, `/redoc` e `/openapi.json` só com `DOCUMENTACAO_API` (desenvolvimento local).

    A configuração só existe depois do lifespan, então as rotas existem sempre e, desligadas,
    respondem o mesmo 404 de uma rota inexistente.
    """

    def exigir_documentacao(request: Request) -> None:
        if not request.app.state.configuracao.documentacao_api:
            raise HTTPException(status_code=404)

    @app.get("/openapi.json", include_in_schema=False)
    async def especificacao(request: Request) -> JSONResponse:
        exigir_documentacao(request)
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    async def swagger(request: Request) -> HTMLResponse:
        exigir_documentacao(request)
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} — docs")

    @app.get("/redoc", include_in_schema=False)
    async def redoc(request: Request) -> HTMLResponse:
        exigir_documentacao(request)
        return get_redoc_html(openapi_url="/openapi.json", title=f"{app.title} — ReDoc")


def criar_app(configuracao: Configuracao | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncGenerator[None, None]:
        config = configuracao or obter_configuracao()
        engine = criar_engine(config)
        app.state.configuracao = config
        app.state.fabrica_sessoes = criar_fabrica_sessoes(engine)
        try:
            yield
        finally:
            await engine.dispose()

    configurar_log()
    app = FastAPI(
        title="Controle de PF e Marmitas",
        lifespan=ciclo_de_vida,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_exception_handler(ErroDeDominio, _tratar_erro_de_dominio)
    app.add_exception_handler(RequestValidationError, _tratar_erro_de_validacao)
    # Exception vai para o ServerErrorMiddleware do Starlette, que devolve esta resposta e
    # depois relança a exceção para o servidor (o uvicorn também a registra).
    app.add_exception_handler(Exception, _tratar_erro_inesperado)
    instalar_seguranca(app)
    _instalar_documentacao(app)
    app.include_router(router_identidade)
    app.include_router(router_usuarios)

    @app.get("/health")
    async def health(request: Request, sessao: SessaoDaRequisicao) -> JSONResponse:
        """Toca o banco com uma consulta trivial, dentro de um tempo máximo (ADR-008)."""
        timeout = request.app.state.configuracao.banco_timeout_segundos
        try:
            await asyncio.wait_for(sessao.execute(text("SELECT 1")), timeout)
        except (SQLAlchemyError, OSError):  # TimeoutError é subclasse de OSError
            return JSONResponse({"status": "indisponivel"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app


app = criar_app()
