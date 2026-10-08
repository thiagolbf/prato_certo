"""Hash de senha com bcrypt, sempre fora do event loop (RN-35, RN-60, ADR-006)."""

import asyncio
import threading

import bcrypt
import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.excecoes import RegraViolada
from app.identidade import senha
from app.identidade.senha import SenhaInvalida, SenhaNova, conferir, gerar_hash


async def test_hash_confere_so_com_a_senha_certa() -> None:
    hash_ = await gerar_hash("segredo-do-joao")

    assert hash_ != "segredo-do-joao"
    assert hash_.startswith("$2b$")
    assert await conferir("segredo-do-joao", hash_)
    assert not await conferir("segredo-do-joaO", hash_)
    assert not await conferir("segredo-do-joao ", hash_)


async def test_mesma_senha_gera_hashes_diferentes() -> None:
    assert await gerar_hash("12345678") != await gerar_hash("12345678")


async def test_hash_roda_fora_do_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    funcoes_em_thread = []
    threads_do_bcrypt = []
    to_thread_original = asyncio.to_thread

    async def espiao(funcao, /, *args, **kwargs):
        funcoes_em_thread.append(funcao)
        return await to_thread_original(funcao, *args, **kwargs)

    def registra_thread(funcao):
        def envolvida(*args, **kwargs):
            threads_do_bcrypt.append(threading.get_ident())
            return funcao(*args, **kwargs)

        return envolvida

    monkeypatch.setattr(senha.asyncio, "to_thread", espiao)
    monkeypatch.setattr(senha.bcrypt, "hashpw", registra_thread(bcrypt.hashpw))
    monkeypatch.setattr(senha.bcrypt, "checkpw", registra_thread(bcrypt.checkpw))

    hash_ = await gerar_hash("segredo-do-joao")
    await conferir("segredo-do-joao", hash_)

    assert len(funcoes_em_thread) == 2
    assert len(threads_do_bcrypt) == 2
    assert threading.get_ident() not in threads_do_bcrypt


async def test_senha_curta_e_recusada() -> None:
    with pytest.raises(SenhaInvalida) as erro:
        await gerar_hash("1234567")

    assert isinstance(erro.value, RegraViolada)
    assert "8 caracteres" in erro.value.mensagem


async def test_espacos_contam_como_caracteres_da_senha() -> None:
    # A senha é guardada como digitada (REVIEW-T-07, R-01): espaços nas pontas contam.
    hash_ = await gerar_hash("  123456")

    assert await conferir("  123456", hash_)
    assert not await conferir("123456", hash_)


async def test_senha_acima_de_72_bytes_e_recusada() -> None:
    # 36 "ç" são 36 caracteres, mas 72 bytes em UTF-8; com mais um, passa do limite do bcrypt.
    assert await gerar_hash("ç" * 36)

    with pytest.raises(SenhaInvalida) as erro:
        await gerar_hash("ç" * 36 + "a")

    assert "72 bytes" in erro.value.mensagem


async def test_senha_acima_de_72_bytes_nao_confere_sem_erro() -> None:
    hash_ = await gerar_hash("a" * 72)

    assert not await conferir("a" * 73, hash_)


def test_senha_nova_no_schema_aplica_os_mesmos_limites() -> None:
    adaptador = TypeAdapter(SenhaNova)

    assert adaptador.validate_python(" 1234567") == " 1234567"
    with pytest.raises(ValidationError):
        adaptador.validate_python("1234567")
    with pytest.raises(ValidationError):
        adaptador.validate_python("a" * 73)
