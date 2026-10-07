"""Cabeçalhos de segurança e redirecionamento para HTTPS (RN-43, RN-44, ADR-006, ADR-008).

O CA-41 fecha do lado Web na T-36; o cookie `Secure` do CA-42 fecha na T-11.
"""

import re
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Configuracao
from app.core.excecoes import Conflito
from app.main import criar_app
from tests.apoio import ConfiguracaoTeste, configuracao_para

CABECALHOS_DE_SEGURANCA = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}
PROXY = ("127.0.0.1", 50000)
ORIGEM_NAO_CONFIAVEL = ("203.0.113.9", 50000)


def _confere_cabecalhos(resposta: Response) -> None:
    for nome, valor in CABECALHOS_DE_SEGURANCA.items():
        assert resposta.headers.get(nome) == valor, nome


async def _app(config_teste: ConfiguracaoTeste, **parametros: object) -> FastAPI:
    app = criar_app(
        configuracao_para(config_teste.url(config_teste.postgres_db_teste), **parametros)
    )

    @app.get("/teste/conflito")
    async def conflito() -> None:
        raise Conflito("já existe")

    @app.get("/teste/falha")
    async def falha() -> None:
        raise RuntimeError("falha inesperada")

    @app.get("/teste/quantidade/{quantidade}")
    async def quantidade(quantidade: int) -> None:
        return None

    return app


def _cliente(
    app: FastAPI, base_url: str = "http://api.teste", origem: tuple[str, int] = PROXY
) -> AsyncClient:
    transporte = ASGITransport(app=app, raise_app_exceptions=False, client=origem)
    return AsyncClient(transport=transporte, base_url=base_url)


@pytest.fixture
async def app_padrao(
    engine: AsyncEngine, config_teste: ConfiguracaoTeste
) -> AsyncIterator[FastAPI]:
    """Sem `FORCAR_HTTPS`, como no desenvolvimento local."""
    app = await _app(config_teste)
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def app_https(engine: AsyncEngine, config_teste: ConfiguracaoTeste) -> AsyncIterator[FastAPI]:
    """Com `FORCAR_HTTPS`, como atrás do proxy do Render."""
    app = await _app(config_teste, forcar_https=True)
    async with app.router.lifespan_context(app):
        yield app


async def test_CA_41_resposta_da_api_carrega_cabecalhos_de_seguranca(app_padrao: FastAPI) -> None:
    async with _cliente(app_padrao) as cliente:
        resposta = await cliente.get("/health")

    assert resposta.status_code == 200
    _confere_cabecalhos(resposta)


@pytest.mark.parametrize(
    ("caminho", "status"),
    [
        ("/rota-inexistente", 404),
        ("/teste/conflito", 409),
        ("/teste/quantidade/abc", 422),
        ("/teste/falha", 500),
    ],
)
async def test_CA_41_resposta_de_erro_tambem_carrega_cabecalhos(
    app_padrao: FastAPI, caminho: str, status: int
) -> None:
    async with _cliente(app_padrao) as cliente:
        resposta = await cliente.get(caminho)

    assert resposta.status_code == status
    _confere_cabecalhos(resposta)


async def test_CA_42_http_redireciona_para_https(app_https: FastAPI) -> None:
    async with _cliente(app_https) as cliente:
        resposta = await cliente.get("/health?origem=ping", headers={"X-Forwarded-Proto": "http"})

    assert resposta.status_code == 308  # permanente, e preserva método e corpo de um POST
    assert resposta.headers["location"] == "https://api.teste/health?origem=ping"
    _confere_cabecalhos(resposta)


async def test_CA_42_https_informado_pelo_proxy_nao_redireciona(app_https: FastAPI) -> None:
    """Atrás do proxy a conexão chega em HTTP; sem ler o cabeçalho, redirecionaria em laço."""
    async with _cliente(app_https) as cliente:
        resposta = await cliente.get("/health", headers={"X-Forwarded-Proto": "https"})

    assert resposta.status_code == 200
    _confere_cabecalhos(resposta)


async def test_CA_42_forwarded_proto_de_origem_nao_confiavel_e_ignorado(app_https: FastAPI) -> None:
    async with _cliente(app_https, origem=ORIGEM_NAO_CONFIAVEL) as cliente:
        resposta = await cliente.get("/health", headers={"X-Forwarded-Proto": "https"})

    assert resposta.status_code == 308
    assert resposta.headers["location"] == "https://api.teste/health"


async def test_https_direto_nao_redireciona(app_https: FastAPI) -> None:
    async with _cliente(app_https, base_url="https://api.teste") as cliente:
        resposta = await cliente.get("/health")

    assert resposta.status_code == 200


async def test_sem_forcar_https_http_nao_redireciona(app_padrao: FastAPI) -> None:
    async with _cliente(app_padrao) as cliente:
        resposta = await cliente.get("/health", headers={"X-Forwarded-Proto": "http"})

    assert resposta.status_code == 200


def test_documentacao_da_api_vem_desligada_por_padrao() -> None:
    assert Configuracao.model_fields["documentacao_api"].default is False


@pytest.mark.parametrize("caminho", ["/docs", "/redoc", "/openapi.json"])
async def test_documentacao_desligada_responde_404_com_csp_restritiva(
    engine: AsyncEngine, config_teste: ConfiguracaoTeste, caminho: str
) -> None:
    """Em produção, nem a lista de rotas da API (inclusive as de ADMIN) fica exposta."""
    app = await _app(config_teste, documentacao_api=False)
    async with app.router.lifespan_context(app), _cliente(app) as cliente:
        resposta = await cliente.get(caminho)

    assert resposta.status_code == 404
    _confere_cabecalhos(resposta)


@pytest.mark.parametrize("caminho", ["/docs", "/redoc"])
async def test_documentacao_ligada_libera_na_csp_o_que_a_pagina_carrega(
    engine: AsyncEngine, config_teste: ConfiguracaoTeste, caminho: str
) -> None:
    app = await _app(config_teste, documentacao_api=True)
    async with app.router.lifespan_context(app), _cliente(app) as cliente:
        resposta = await cliente.get(caminho)
        especificacao = await cliente.get("/openapi.json")

    assert resposta.status_code == 200
    csp = resposta.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp
    origens = set(re.findall(r'(?:src|href)="(https://[^/"]+)', resposta.text))
    assert origens  # a página carrega recursos externos
    for origem in origens:
        assert origem in csp, origem
    assert "/health" in especificacao.json()["paths"]
    assert "/docs" not in especificacao.json()["paths"]
    # O restante da resposta continua com os outros três cabeçalhos.
    assert resposta.headers["x-frame-options"] == "DENY"
    assert resposta.headers["x-content-type-options"] == "nosniff"
