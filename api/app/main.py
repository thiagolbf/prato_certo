"""Ponto de entrada da API: monta a aplicação e as rotas transversais."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Configuracao, obter_configuracao
from app.core.db import criar_engine, criar_fabrica_sessoes, obter_sessao


def criar_app(configuracao: Configuracao | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        config = configuracao or obter_configuracao()
        engine = criar_engine(config)
        app.state.configuracao = config
        app.state.fabrica_sessoes = criar_fabrica_sessoes(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="Controle de PF e Marmitas", lifespan=ciclo_de_vida)

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
