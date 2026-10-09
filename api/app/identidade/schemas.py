"""Contrato HTTP do módulo identidade (ADR-009): schemas de entrada e de resposta.

Entrada herda de `ModeloEstrito`; senha usa `TextoLiteral`, para chegar como digitada (RN-60).
"""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.schemas import ModeloEstrito, TextoLiteral
from app.identidade.modelos import Perfil
from app.identidade.servico_sessao import UsuarioAutenticado


class LoginEntrada(ModeloEstrito):
    login: Annotated[str, Field(min_length=1, max_length=60)]
    senha: TextoLiteral


class RespostaUsuario(BaseModel):
    nome: str
    perfil: Perfil
    dia_operacional: date

    @classmethod
    def de(cls, usuario: UsuarioAutenticado, dia_operacional: date) -> "RespostaUsuario":
        return cls(nome=usuario.nome, perfil=usuario.perfil, dia_operacional=dia_operacional)
