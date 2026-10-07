"""Entrada validada por schema estrito e corpo com tamanho máximo (RN-46, ADR-009)."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient, Response
from pydantic import Field
from starlette.types import Message

from app.core.config import Configuracao
from app.core.schemas import ModeloEstrito, TextoLiteral
from app.core.seguranca import LimiteDeCorpo
from app.main import criar_app

LIMITE = 16 * 1024


class Cadastro(ModeloEstrito):
    nome: str


class DefinirSenha(ModeloEstrito):
    login: str
    senha: Annotated[TextoLiteral, Field(min_length=8)]


@pytest.fixture
async def chamadas() -> list[int]:
    """Tamanho do corpo que cada chamada da rota recebeu: prova se a rota rodou."""
    return []


@pytest.fixture
async def cliente_entrada(
    configuracao: Configuracao, chamadas: list[int]
) -> AsyncIterator[AsyncClient]:
    app: FastAPI = criar_app(configuracao.model_copy(update={"corpo_maximo_bytes": LIMITE}))

    @app.post("/teste/cadastro")
    async def cadastro(entrada: Cadastro) -> dict[str, str]:
        return {"nome": entrada.nome}

    @app.post("/teste/senha")
    async def definir_senha(entrada: DefinirSenha) -> dict[str, str]:
        return {"login": entrada.login, "senha": entrada.senha}

    @app.post("/teste/corpo")
    async def corpo(request: Request) -> dict[str, int]:
        recebido = await request.body()
        chamadas.append(len(recebido))
        return {"bytes": len(recebido)}

    @app.get("/teste/sem-corpo")
    async def sem_corpo() -> dict[str, bool]:
        chamadas.append(0)
        return {"ok": True}

    async with app.router.lifespan_context(app):
        transporte = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transporte, base_url="http://teste") as cliente:
            yield cliente


async def _em_pedacos(total: int, pedaco: int = 4096) -> AsyncIterator[bytes]:
    """Corpo em fluxo, sem Content-Length (Transfer-Encoding: chunked)."""
    enviado = 0
    while enviado < total:
        tamanho = min(pedaco, total - enviado)
        enviado += tamanho
        yield b"x" * tamanho


def _confere_413(resposta: Response) -> None:
    assert resposta.status_code == 413
    assert resposta.json() == {"detail": "Corpo da requisição acima do limite."}
    assert resposta.headers["x-content-type-options"] == "nosniff"  # passa pelos cabeçalhos


async def test_CA_44_campo_desconhecido_e_rejeitado(cliente_entrada: AsyncClient) -> None:
    resposta = await cliente_entrada.post(
        "/teste/cadastro", json={"nome": "Frango", "perfil": "ADMIN"}
    )

    assert resposta.status_code == 422
    [erro] = resposta.json()["detail"]
    assert erro["loc"] == ["body", "perfil"]
    assert erro["type"] == "extra_forbidden"


async def test_texto_chega_sem_espacos_nas_pontas(cliente_entrada: AsyncClient) -> None:
    resposta = await cliente_entrada.post("/teste/cadastro", json={"nome": "  Frango grelhado  "})

    assert resposta.status_code == 200
    assert resposta.json() == {"nome": "Frango grelhado"}


async def test_CA_45_corpo_acima_do_limite_e_recusado(
    cliente_entrada: AsyncClient, chamadas: list[int]
) -> None:
    resposta = await cliente_entrada.post("/teste/corpo", content=b"x" * (LIMITE + 1))

    _confere_413(resposta)
    assert chamadas == []  # recusado antes de chegar à rota


async def test_CA_45_corpo_sem_content_length_acima_do_limite_e_recusado(
    cliente_entrada: AsyncClient, chamadas: list[int]
) -> None:
    resposta = await cliente_entrada.post("/teste/corpo", content=_em_pedacos(LIMITE + 1))

    assert "content-length" not in resposta.request.headers
    _confere_413(resposta)
    assert chamadas == []


async def test_CA_45_content_length_acima_do_limite_e_recusado_mesmo_em_rota_sem_corpo(
    cliente_entrada: AsyncClient, chamadas: list[int]
) -> None:
    resposta = await cliente_entrada.request("GET", "/teste/sem-corpo", content=b"x" * (LIMITE + 1))

    _confere_413(resposta)
    assert chamadas == []


@pytest.mark.parametrize("em_fluxo", [False, True])
async def test_corpo_no_limite_chega_inteiro_a_rota(
    cliente_entrada: AsyncClient, chamadas: list[int], em_fluxo: bool
) -> None:
    conteudo = _em_pedacos(LIMITE) if em_fluxo else b"x" * LIMITE

    resposta = await cliente_entrada.post("/teste/corpo", content=conteudo)

    assert resposta.status_code == 200
    assert resposta.json() == {"bytes": LIMITE}
    assert chamadas == [LIMITE]


async def test_requisicao_sem_corpo_passa(
    cliente_entrada: AsyncClient, chamadas: list[int]
) -> None:
    resposta = await cliente_entrada.get("/teste/sem-corpo")

    assert resposta.status_code == 200
    assert chamadas == [0]


async def test_senha_chega_exatamente_como_digitada(cliente_entrada: AsyncClient) -> None:
    """Senha não é normalizada: o hash é do que o usuário digitou (RN-60)."""
    resposta = await cliente_entrada.post(
        "/teste/senha", json={"login": "  joao  ", "senha": "  minha senha  "}
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"login": "joao", "senha": "  minha senha  "}


async def test_espaco_digitado_conta_no_minimo_da_senha(cliente_entrada: AsyncClient) -> None:
    """8 caracteres digitados, com espaço na ponta: a API conta 8, como a tela (RN-60)."""
    aceita = await cliente_entrada.post("/teste/senha", json={"login": "joao", "senha": "abc1234 "})
    curta = await cliente_entrada.post("/teste/senha", json={"login": "joao", "senha": "abc1234"})

    assert aceita.status_code == 200
    assert curta.status_code == 422
    assert curta.json()["detail"][0]["type"] == "string_too_short"


@pytest.mark.parametrize("declarado", ["²".encode("latin-1"), b"-1", b"abc"])
async def test_content_length_malformado_cai_na_contagem_do_fluxo(declarado: bytes) -> None:
    """O uvicorn já recusa esses valores; o middleware não pode depender disso para não quebrar."""
    chamadas: list[bytes] = []
    respostas: list[Message] = []
    mensagens = [{"type": "http.request", "body": b"x" * (LIMITE + 1), "more_body": False}]

    async def aplicacao(scope: object, receive: object, send: object) -> None:
        chamadas.append(b"chamada")

    async def receber() -> Message:
        return mensagens.pop(0)

    async def enviar(mensagem: Message) -> None:
        respostas.append(mensagem)

    configuracao = SimpleNamespace(corpo_maximo_bytes=LIMITE)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/teste/corpo",
        "headers": [(b"content-length", declarado)],
        "app": SimpleNamespace(state=SimpleNamespace(configuracao=configuracao)),
    }

    await LimiteDeCorpo(aplicacao)(scope, receber, enviar)

    assert chamadas == []
    assert respostas[0]["status"] == 413
