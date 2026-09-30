import asyncio
import time

from httpx import ASGITransport, AsyncClient

from app.main import criar_app
from tests.apoio import ConfiguracaoTeste, configuracao_para


async def _get_health(database_url: str, **parametros: object) -> tuple[int, dict, float]:
    app = criar_app(configuracao_para(database_url, **parametros))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://teste") as cliente,
    ):
        inicio = time.monotonic()
        resposta = await cliente.get("/health")
        return resposta.status_code, resposta.json(), time.monotonic() - inicio


async def test_health_responde_200_consultando_o_banco(cliente: AsyncClient) -> None:
    resposta = await cliente.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


async def test_health_responde_503_sem_banco(config_teste: ConfiguracaoTeste) -> None:
    status, corpo, _ = await _get_health(config_teste.url("banco_que_nao_existe"))

    assert status == 503
    assert corpo == {"status": "indisponivel"}


async def test_health_responde_503_dentro_do_timeout_quando_o_banco_nao_responde() -> None:
    """Banco que aceita a conexão e nunca responde: o /health não pode ficar pendurado."""

    async def aceita_e_nao_responde(
        leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter
    ) -> None:
        await leitor.read()  # só termina quando o cliente desiste e fecha a conexão
        escritor.close()

    servidor = await asyncio.start_server(aceita_e_nao_responde, "127.0.0.1", 0)
    porta = servidor.sockets[0].getsockname()[1]
    async with servidor:
        status, corpo, duracao = await _get_health(
            f"postgresql+asyncpg://usuario:senha@127.0.0.1:{porta}/pf",
            banco_timeout_segundos=0.5,
        )

    assert status == 503
    assert corpo == {"status": "indisponivel"}
    assert duracao < 3
