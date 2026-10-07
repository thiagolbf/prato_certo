"""Middlewares de segurança: cabeçalhos em toda resposta e HTTPS obrigatório (RN-43, RN-44).

Ordem, de fora para dentro, montada por `instalar_seguranca`:
cabeçalhos → leitura do proxy → redirecionamento para HTTPS → aplicação.
A resposta 500 nasce no `ServerErrorMiddleware` do Starlette, por fora de todos eles; por
isso o handler de erro interno também aplica `CABECALHOS_DE_SEGURANCA` (ver `app/main.py`).

A configuração só existe depois do lifespan (`app.state.configuracao`, ver `criar_app`), então
os middlewares a leem na requisição, nunca na montagem.
"""

from fastapi import FastAPI
from starlette.datastructures import URL, MutableHeaders
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import Configuracao

CABECALHOS_DE_SEGURANCA = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # A API devolve JSON: nada a carregar, nada a embutir.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# Exceção única: as páginas de documentação do FastAPI, só quando `DOCUMENTACAO_API` está
# ligada (desenvolvimento local). Elas carregam script e estilo de CDN e usam script inline.
ROTAS_DOCUMENTACAO = frozenset({"/docs", "/redoc"})
CSP_DOCUMENTACAO = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "worker-src blob:; "
    "frame-ancestors 'none'"
)


class CabecalhosDeSeguranca:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        documentacao = scope["path"] in ROTAS_DOCUMENTACAO and _configuracao(scope).documentacao_api

        async def enviar(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                cabecalhos = MutableHeaders(scope=mensagem)
                for nome, valor in CABECALHOS_DE_SEGURANCA.items():
                    cabecalhos[nome] = valor
                if documentacao:
                    cabecalhos["Content-Security-Policy"] = CSP_DOCUMENTACAO
            await send(mensagem)

        await self.app(scope, receive, enviar)


def _configuracao(scope: Scope) -> Configuracao:
    return scope["app"].state.configuracao


class LeituraDoProxy:
    """`ProxyHeadersMiddleware` do uvicorn com os proxies confiáveis da configuração.

    Só aceita `X-Forwarded-Proto` e `X-Forwarded-For` de conexão vinda de um endereço em
    `PROXIES_CONFIAVEIS`; de qualquer outro, ignora os cabeçalhos.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._proxy: ProxyHeadersMiddleware | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self._proxy is None:
            confiaveis = _configuracao(scope).proxies_confiaveis
            self._proxy = ProxyHeadersMiddleware(self.app, trusted_hosts=confiaveis)
        await self._proxy(scope, receive, send)


class RedirecionaParaHttps:
    """Com `FORCAR_HTTPS`, redireciona HTTP para HTTPS em definitivo (308: preserva método e corpo).

    Decide pelo `scope["scheme"]`, que a `LeituraDoProxy` ajusta a partir do
    `X-Forwarded-Proto` só quando a conexão vem de um proxy confiável.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["scheme"] == "https"
            or not _configuracao(scope).forcar_https
        ):
            await self.app(scope, receive, send)
            return
        url = URL(scope=scope)
        netloc = url.hostname if url.port in (None, 80) else url.netloc
        resposta = RedirectResponse(url.replace(scheme="https", netloc=netloc), status_code=308)
        await resposta(scope, receive, send)


def instalar_seguranca(app: FastAPI) -> None:
    # `add_middleware` põe o último adicionado por fora.
    app.add_middleware(RedirecionaParaHttps)
    app.add_middleware(LeituraDoProxy)
    app.add_middleware(CabecalhosDeSeguranca)
