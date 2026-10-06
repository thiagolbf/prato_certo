"""Ponto de entrada da API: monta a aplicação, as rotas transversais e o tratamento de erros."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Configuracao, obter_configuracao
from app.core.db import criar_engine, criar_fabrica_sessoes, obter_sessao
from app.core.excecoes import (
    Conflito,
    ErroDeDominio,
    NaoAutenticado,
    NaoEncontrado,
    RegraViolada,
    SemPermissao,
)
from app.core.log import configurar_log

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
    return JSONResponse({"detail": MENSAGEM_ERRO_INTERNO}, status_code=500)


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
    app = FastAPI(title="Controle de PF e Marmitas", lifespan=ciclo_de_vida)
    app.add_exception_handler(ErroDeDominio, _tratar_erro_de_dominio)
    app.add_exception_handler(RequestValidationError, _tratar_erro_de_validacao)
    # Exception vai para o ServerErrorMiddleware do Starlette, que devolve esta resposta e
    # depois relança a exceção para o servidor (o uvicorn também a registra).
    app.add_exception_handler(Exception, _tratar_erro_inesperado)

    @app.get("/health")
    async def health(
        request: Request, sessao: Annotated[AsyncSession, Depends(obter_sessao)]
    ) -> JSONResponse:
        """Toca o banco com uma consulta trivial, dentro de um tempo máximo (ADR-008)."""
        timeout = request.app.state.configuracao.banco_timeout_segundos
        try:
            await asyncio.wait_for(sessao.execute(text("SELECT 1")), timeout)
        except (SQLAlchemyError, OSError):  # TimeoutError é subclasse de OSError
            return JSONResponse({"status": "indisponivel"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app


app = criar_app()
