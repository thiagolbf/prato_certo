"""Middlewares de segurança: cabeçalhos, HTTPS obrigatório e limite de corpo (RN-43, RN-44, RN-46).

Ordem, de fora para dentro, montada por `instalar_seguranca`:
cabeçalhos → leitura do proxy → redirecionamento para HTTPS → limite de corpo → aplicação.
A resposta 500 nasce no `ServerErrorMiddleware` do Starlette, por fora de todos eles; por
isso o handler de erro interno também aplica `CABECALHOS_DE_SEGURANCA` (ver `app/main.py`).

A configuração só existe depois do lifespan (`app.state.configuracao`, ver `criar_app`), então
os middlewares a leem na requisição, nunca na montagem.
"""

from fastapi import FastAPI
from starlette.datastructures import URL, Headers, MutableHeaders
from starlette.responses import JSONResponse, RedirectResponse
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


class LimiteDeCorpo:
    """Recusa com 413, antes de a rota rodar, corpo acima de `CORPO_MAXIMO_BYTES` (RN-46).

    Com `Content-Length` acima do limite, recusa sem ler nada. Sem ele (corpo em fluxo), lê
    até o limite e para no primeiro byte a mais. O corpo aceito, de no máximo o limite, é
    entregue à aplicação já lido: interromper a leitura dentro da rota faria o FastAPI
    responder 400 em vez de 413.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limite = _configuracao(scope).corpo_maximo_bytes
        declarado = Headers(scope=scope).get("content-length", "")
        # isdecimal só em ASCII: "²" passa no isdigit(), mas int("²") falha.
        if declarado.isascii() and declarado.isdecimal() and int(declarado) > limite:
            await _recusar_corpo(scope, receive, send)
            return

        mensagens: list[Message] = []
        recebidos = 0
        while True:
            mensagem = await receive()
            if mensagem["type"] == "http.disconnect":
                return
            recebidos += len(mensagem.get("body", b""))
            if recebidos > limite:
                await _recusar_corpo(scope, receive, send)
                return
            mensagens.append(mensagem)
            if not mensagem.get("more_body", False):
                break

        async def repetir_corpo() -> Message:
            # Depois do corpo, o `receive` original segue avisando a desconexão do cliente.
            return mensagens.pop(0) if mensagens else await receive()

        await self.app(scope, repetir_corpo, send)


async def _recusar_corpo(scope: Scope, receive: Receive, send: Send) -> None:
    resposta = JSONResponse({"detail": "Corpo da requisição acima do limite."}, status_code=413)
    await resposta(scope, receive, send)


def instalar_seguranca(app: FastAPI) -> None:
    # `add_middleware` põe o último adicionado por fora.
    app.add_middleware(LimiteDeCorpo)
    app.add_middleware(RedirecionaParaHttps)
    app.add_middleware(LeituraDoProxy)
    app.add_middleware(CabecalhosDeSeguranca)
