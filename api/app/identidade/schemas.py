"""Contrato HTTP do módulo identidade (ADR-009): schemas de entrada e de resposta.

Entrada herda de `ModeloEstrito`; senha usa `TextoLiteral`, para chegar como digitada (RN-60).
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.core.schemas import ModeloEstrito, TextoLiteral
from app.identidade.modelos import Perfil
from app.identidade.senha import SenhaNova
from app.identidade.servico_sessao import UsuarioAutenticado


def _validar_nome(valor: str) -> str:
    if not 1 <= len(valor) <= 60:
        raise ValueError("O nome precisa ter de 1 a 60 caracteres.")
    return valor


def _validar_login(valor: str) -> str:
    if not 1 <= len(valor) <= 30 or any(caractere.isspace() for caractere in valor):
        raise ValueError("O login precisa ter de 1 a 30 caracteres, sem espaços.")
    return valor


# Limites da SPEC-UI-001 (lacuna 16), iguais aos do cadastro e do comando técnico (RN-60).
Nome = Annotated[str, AfterValidator(_validar_nome)]
Login = Annotated[str, AfterValidator(_validar_login)]


class LoginEntrada(ModeloEstrito):
    login: Annotated[str, Field(min_length=1, max_length=60)]
    senha: TextoLiteral


class NovoUsuario(ModeloEstrito):
    """Cadastro pela API: sem campo de perfil, o usuário criado é sempre Operador (RN-34)."""

    nome: Nome
    login: Login
    senha: SenhaNova


class RedefinirSenhaEntrada(ModeloEstrito):
    senha: SenhaNova


class TrocarSenhaEntrada(ModeloEstrito):
    # A senha atual chega como digitada; a nova segue os limites da RN-60.
    senha_atual: TextoLiteral
    senha_nova: SenhaNova


class UsuarioListado(BaseModel):
    id: int
    nome: str
    login: str
    perfil: Perfil
    ativo: bool
    # Só preenchido enquanto a conta está bloqueada agora (RN-52).
    bloqueado_ate: datetime | None


class RespostaUsuario(BaseModel):
    nome: str
    perfil: Perfil
    dia_operacional: date

    @classmethod
    def de(cls, usuario: UsuarioAutenticado, dia_operacional: date) -> "RespostaUsuario":
        return cls(nome=usuario.nome, perfil=usuario.perfil, dia_operacional=dia_operacional)
