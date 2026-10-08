"""Hash de senha com bcrypt, sempre fora do event loop (RN-35, RN-60, ADR-006).

O hash é caro de propósito. Rodado direto numa `async def`, uma rajada de logins congelaria
o registro de vendas de todo mundo (seção 10 da proposta): por isso toda chamada ao bcrypt
passa por `asyncio.to_thread`. Pacote `bcrypt` da pyca, nunca `passlib` (ADR-006).
"""

import asyncio
from typing import Annotated

import bcrypt
from pydantic import AfterValidator

from app.core.excecoes import RegraViolada
from app.core.schemas import TextoLiteral

TAMANHO_MINIMO = 8
# O bcrypt só considera os primeiros 72 bytes, e a versão 5 recusa o que passar disso.
# O limite é em bytes UTF-8: "ç" ocupa 2.
TAMANHO_MAXIMO_BYTES = 72
CUSTO = 12


class SenhaInvalida(RegraViolada):
    """A senha nova não cabe nos limites da RN-60."""


def validar(senha: str) -> str:
    """Devolve a senha intacta, ou recusa a que tem menos de 8 caracteres ou mais de 72 bytes."""
    if len(senha) < TAMANHO_MINIMO:
        raise SenhaInvalida(f"A senha precisa ter no mínimo {TAMANHO_MINIMO} caracteres.")
    if len(senha.encode()) > TAMANHO_MAXIMO_BYTES:
        raise SenhaInvalida(
            f"A senha pode ter no máximo {TAMANHO_MAXIMO_BYTES} bytes (72 caracteres sem acento)."
        )
    return senha


def _cabe_no_bcrypt(senha: str) -> str:
    # Erro de validação do Pydantic precisa ser ValueError; a mensagem é a mesma do domínio.
    try:
        return validar(senha)
    except SenhaInvalida as erro:
        raise ValueError(erro.mensagem) from None


# Senha a cadastrar, redefinir ou trocar, nos schemas de entrada: chega como digitada
# (sem corte de espaços, REVIEW-T-07, R-01) e com os limites da RN-60, conferidos por
# `validar`, para o schema e o domínio darem a mesma mensagem.
SenhaNova = Annotated[TextoLiteral, AfterValidator(_cabe_no_bcrypt)]


async def gerar_hash(senha: str) -> str:
    validar(senha)
    hash_ = await asyncio.to_thread(bcrypt.hashpw, senha.encode(), bcrypt.gensalt(CUSTO))
    return hash_.decode()


async def conferir(senha: str, senha_hash: str) -> bool:
    """Senha acima do limite nunca foi cadastrada: não confere, sem erro e sem gastar o hash."""
    senha_em_bytes = senha.encode()
    if len(senha_em_bytes) > TAMANHO_MAXIMO_BYTES:
        return False
    return await asyncio.to_thread(bcrypt.checkpw, senha_em_bytes, senha_hash.encode())
