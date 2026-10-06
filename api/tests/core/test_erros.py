"""Exceções de domínio, respostas de erro sem detalhe e log higienizado (RN-45, RN-48, ADR-009)."""

import io
import json
import logging
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Configuracao
from app.core.excecoes import (
    Conflito,
    ErroDeDominio,
    NaoAutenticado,
    NaoEncontrado,
    RegraViolada,
    SemPermissao,
)
from app.core.log import configurar_log
from app.main import criar_app

MENSAGEM = "Mensagem de negócio"
FALHA = "SELECT senha_hash FROM usuario -- C:\\api\\app\\vendas\\repositorio.py"

ERROS_DE_DOMINIO: dict[str, type[ErroDeDominio]] = {
    classe.__name__: classe
    for classe in (NaoEncontrado, Conflito, RegraViolada, NaoAutenticado, SemPermissao)
}


class ProteinaEmUso(Conflito):
    """Subclasse como as que os módulos vão criar."""


class Entrada(BaseModel):
    senha: str
    quantidade: int


@pytest.fixture
async def app_erros(configuracao: Configuracao) -> AsyncIterator[FastAPI]:
    app = criar_app(configuracao)

    @app.get("/teste/falha")
    async def falha() -> None:
        raise RuntimeError(FALHA)

    @app.get("/teste/dominio/{nome}")
    async def dominio(nome: str) -> None:
        classe = ProteinaEmUso if nome == "ProteinaEmUso" else ERROS_DE_DOMINIO[nome]
        raise classe(MENSAGEM)

    @app.post("/teste/validacao")
    async def validacao(entrada: Entrada) -> None:
        return None

    @app.get("/teste/log")
    async def log_descuidado(request: Request) -> None:
        # Código descuidado que despeja os cabeçalhos no log: o filtro ainda protege.
        logging.getLogger("app.teste").info(
            "requisição recebida", extra={"cabecalhos": dict(request.headers)}
        )

    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
def log(app_erros: FastAPI) -> Iterator[io.StringIO]:
    """Saída do log da aplicação; criada depois do app, que configura o log na saída padrão."""
    destino = io.StringIO()
    configurar_log(destino)
    yield destino
    configurar_log()


@pytest.fixture
async def cliente_erros(app_erros: FastAPI, log: io.StringIO) -> AsyncIterator[AsyncClient]:
    # Sem propagar a exceção ao teste: o que interessa é a resposta que o cliente recebe.
    transporte = ASGITransport(app=app_erros, raise_app_exceptions=False)
    async with AsyncClient(transport=transporte, base_url="http://teste") as cliente:
        yield cliente


def _registros(log: io.StringIO) -> list[dict]:
    return [json.loads(linha) for linha in log.getvalue().splitlines()]


async def test_CA_46_erro_interno_nao_vaza_detalhe(
    cliente_erros: AsyncClient, log: io.StringIO
) -> None:
    resposta = await cliente_erros.get("/teste/falha")

    assert resposta.status_code == 500
    assert resposta.json() == {"detail": "Erro interno. Tente novamente."}
    for vazamento in ("Traceback", "RuntimeError", "SELECT", "senha_hash", "C:\\", ".py"):
        assert vazamento not in resposta.text

    [registro] = _registros(log)
    assert registro["nivel"] == "ERROR"
    assert registro["metodo"] == "GET"
    assert registro["caminho"] == "/teste/falha"
    assert "Traceback" in registro["excecao"]
    assert f"RuntimeError: {FALHA}" in registro["excecao"]


async def test_erro_de_banco_nao_leva_parametros_da_consulta_ao_log(
    engine: AsyncEngine, app_erros: FastAPI, cliente_erros: AsyncClient, log: io.StringIO
) -> None:
    """O SQLAlchemy põe `[parameters: ...]` na mensagem; num INSERT de usuário, o hash (RN-45).

    A falha não depende do valor (como uma violação de constraint num INSERT de usuário), então
    ele só apareceria pela lista de parâmetros.
    """

    @app_erros.get("/teste/falha-banco")
    async def falha_banco(request: Request) -> None:
        async with request.app.state.fabrica_sessoes() as sessao:
            await sessao.execute(
                text("SELECT CAST(:senha_hash AS text), 1 / 0"),
                {"senha_hash": "$2b$12$HASHSECRETO"},
            )

    resposta = await cliente_erros.get("/teste/falha-banco")

    assert resposta.status_code == 500
    assert "HASHSECRETO" not in log.getvalue()
    # O SQL continua no log: é o que permite diagnosticar a falha.
    assert "division by zero" in _registros(log)[0]["excecao"]
    assert "SELECT CAST(" in _registros(log)[0]["excecao"]


@pytest.mark.parametrize(
    ("nome", "status"),
    [
        ("NaoEncontrado", 404),
        ("Conflito", 409),
        ("RegraViolada", 422),
        ("NaoAutenticado", 401),
        ("SemPermissao", 403),
        ("ProteinaEmUso", 409),
    ],
)
async def test_excecao_de_dominio_vira_status_http(
    cliente_erros: AsyncClient, log: io.StringIO, nome: str, status: int
) -> None:
    resposta = await cliente_erros.get(f"/teste/dominio/{nome}")

    assert resposta.status_code == status
    assert resposta.json() == {"detail": MENSAGEM}
    assert _registros(log) == []  # erro de regra é fluxo de negócio, não falha do sistema


async def test_erro_de_dominio_sem_base_conhecida_vira_500_neutro(
    app_erros: FastAPI, cliente_erros: AsyncClient, log: io.StringIO
) -> None:
    @app_erros.get("/teste/dominio-cru")
    async def dominio_cru() -> None:
        raise ErroDeDominio("sem base: defeito de programação")

    resposta = await cliente_erros.get("/teste/dominio-cru")

    assert resposta.status_code == 500
    assert resposta.json() == {"detail": "Erro interno. Tente novamente."}
    assert "sem base" in _registros(log)[0]["excecao"]


def test_excecoes_de_dominio_nao_conhecem_http() -> None:
    """As entidades levantam estas exceções; a tradução para HTTP fica fora (ADR-009, item 7)."""
    fonte = (Path(__file__).resolve().parents[2] / "app" / "core" / "excecoes.py").read_text(
        encoding="utf-8"
    )

    assert "fastapi" not in fonte
    assert "starlette" not in fonte
    assert NaoEncontrado(MENSAGEM).mensagem == MENSAGEM


async def test_erro_de_validacao_nao_ecoa_o_corpo_recebido(cliente_erros: AsyncClient) -> None:
    resposta = await cliente_erros.post("/teste/validacao", json={"senha": "segredo-do-corpo"})

    assert resposta.status_code == 422
    assert "segredo-do-corpo" not in resposta.text
    [erro] = resposta.json()["detail"]
    assert erro == {"loc": ["body", "quantidade"], "msg": "Field required", "type": "missing"}


async def test_log_nao_registra_cookie_nem_authorization(
    cliente_erros: AsyncClient, log: io.StringIO
) -> None:
    cabecalhos = {
        "Cookie": "sessao=valor-do-cookie",
        "Authorization": "Bearer valor-do-token",
        "X-Teste": "valor-visivel",
    }

    await cliente_erros.get("/teste/log", headers=cabecalhos)
    await cliente_erros.get("/teste/falha", headers=cabecalhos)

    saida = log.getvalue()
    assert "valor-do-cookie" not in saida
    assert "valor-do-token" not in saida
    registro = _registros(log)[0]
    assert registro["cabecalhos"]["cookie"] == "[removido]"
    assert registro["cabecalhos"]["authorization"] == "[removido]"
    assert registro["cabecalhos"]["x-teste"] == "valor-visivel"


def test_log_nao_registra_senha_hash_nem_corpo(log: io.StringIO) -> None:
    usuario = {"login": "joao", "senha": "s3gr3d0", "senha_hash": "$2b$12$abc"}

    logging.getLogger("app.teste").info(
        "login",
        extra={
            "usuario": usuario,
            "corpo": '{"senha": "s3gr3d0"}',
            "cabecalhos_asgi": [(b"cookie", b"sessao=abc123")],
        },
    )

    saida = log.getvalue()
    for segredo in ("s3gr3d0", "$2b$12$abc", "abc123"):
        assert segredo not in saida
    registro = _registros(log)[0]
    assert registro["usuario"]["login"] == "joao"
    assert registro["corpo"] == "[removido]"
    # O filtro trabalha sobre cópia: o dado de quem chamou não é alterado.
    assert usuario["senha"] == "s3gr3d0"


def test_log_e_estruturado_em_json(log: io.StringIO) -> None:
    logging.getLogger("app.teste").warning("aviso %s", "formatado", extra={"venda_id": 7})

    [registro] = _registros(log)
    assert registro["nivel"] == "WARNING"
    assert registro["logger"] == "app.teste"
    assert registro["mensagem"] == "aviso formatado"
    assert registro["venda_id"] == 7
    assert registro["instante"].endswith("+00:00")


def test_extra_com_nome_de_campo_do_formato_nao_o_sobrescreve(log: io.StringIO) -> None:
    logging.getLogger("app.teste").info(
        "mensagem real", extra={"mensagem": "falsa", "nivel": "DEBUG", "instante": "ontem"}
    )

    [registro] = _registros(log)
    assert registro["mensagem"] == "mensagem real"
    assert registro["nivel"] == "INFO"
    assert registro["instante"].endswith("+00:00")
    # O dado não some: vai para um campo prefixado.
    assert registro["extra_mensagem"] == "falsa"
    assert registro["extra_nivel"] == "DEBUG"
