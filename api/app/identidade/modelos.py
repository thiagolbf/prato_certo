"""Entidades do módulo identidade: Usuario, Perfil e Sessao (RN-34, RN-36, RN-37, RN-54, ADR-009).

A regra do bloqueio por conta vive na entidade; o service só carrega, chama e persiste.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo_base import Base
from app.core.tempo import exigir_instante_com_fuso


class Perfil(StrEnum):
    ADMIN = "ADMIN"
    OPERADOR = "OPERADOR"


@dataclass(frozen=True)
class PoliticaDeBloqueio:
    """Parâmetros do bloqueio por conta (RN-37), vindos da configuração.

    A entidade recebe a política; não lê o ambiente (PLAN-001, T-08).
    """

    tentativas: int
    minutos: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.tentativas < 1:
            raise ValueError("tentativas precisa ser ao menos 1")
        if not self.minutos or any(m <= 0 for m in self.minutos):
            raise ValueError("a sequência de minutos precisa de valores positivos")

    def duracao_do_bloqueio(self, numero: int) -> timedelta:
        """Duração do `numero`-ésimo bloqueio (1, 2, ...); depois do último, fica no teto."""
        return timedelta(minutes=self.minutos[min(numero, len(self.minutos)) - 1])


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estabelecimento.id"))
    nome: Mapped[str] = mapped_column(Text)
    login: Mapped[str] = mapped_column(Text)
    senha_hash: Mapped[str] = mapped_column(Text)
    perfil: Mapped[Perfil] = mapped_column(
        Enum(Perfil, name="perfil", native_enum=False, create_constraint=True, length=8)
    )
    ativo: Mapped[bool] = mapped_column(Boolean)
    # Estado do bloqueio por conta: colunas da conta, não memória de processo (RN-37).
    falhas_consecutivas: Mapped[int] = mapped_column(Integer)
    bloqueios: Mapped[int] = mapped_column(Integer)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @classmethod
    def criar(
        cls,
        *,
        estabelecimento_id: int,
        nome: str,
        login: str,
        senha_hash: str,
        perfil: Perfil,
    ) -> Usuario:
        """Conta nova: ativa, sem falhas e sem bloqueio. O login é guardado como digitado."""
        return cls(
            estabelecimento_id=estabelecimento_id,
            nome=nome,
            login=login,
            senha_hash=senha_hash,
            perfil=perfil,
            ativo=True,
            falhas_consecutivas=0,
            bloqueios=0,
            bloqueado_ate=None,
        )

    def registrar_falha_login(self, agora: datetime, politica: PoliticaDeBloqueio) -> None:
        """Conta a falha; ao atingir o limite, bloqueia pelo próximo tempo da sequência (RN-37).

        O contador recomeça a cada bloqueio: o seguinte exige outras `tentativas` falhas.
        Com a conta bloqueada, a tentativa nem chega a conferir senha e não conta: senão,
        quem digitasse errado numa conta alheia a levaria ao teto em segundos.
        """
        if self.esta_bloqueado(agora):
            return
        self.falhas_consecutivas += 1
        if self.falhas_consecutivas >= politica.tentativas:
            self.bloqueios += 1
            self.bloqueado_ate = agora + politica.duracao_do_bloqueio(self.bloqueios)
            self.falhas_consecutivas = 0

    def registrar_login_ok(self) -> None:
        """Zera o contador de falhas (RN-37). A progressão dos bloqueios não recomeça."""
        self.falhas_consecutivas = 0

    def redefinir_senha(self, senha_hash: str) -> None:
        """Troca a senha e libera a conta, para entrar sem esperar o bloqueio (RN-52, RN-53).

        Como no login com sucesso, a progressão dos bloqueios não recomeça.
        """
        self.senha_hash = senha_hash
        self.falhas_consecutivas = 0
        self.bloqueado_ate = None

    def esta_bloqueado(self, agora: datetime) -> bool:
        exigir_instante_com_fuso(agora)
        return self.bloqueado_ate is not None and agora < self.bloqueado_ate

    def desativar(self) -> None:
        """Nunca exclusão: a conta fica, com a autoria das vendas que registrou (RN-34)."""
        self.ativo = False

    def reativar(self) -> None:
        """Volta a autenticar com a mesma conta (RN-34)."""
        self.ativo = True


@dataclass(frozen=True)
class PoliticaDeSessao:
    """Inatividade máxima da sessão por perfil (RN-36, ADR-006), vinda da configuração.

    A do ADMIN é mais curta: é o perfil que altera preço e cadastro.
    """

    inatividade_admin: timedelta
    inatividade_operador: timedelta

    def __post_init__(self) -> None:
        if self.inatividade_admin <= timedelta(0) or self.inatividade_operador <= timedelta(0):
            raise ValueError("a inatividade da sessão precisa ser positiva")

    def inatividade_para(self, perfil: Perfil) -> timedelta:
        return self.inatividade_admin if perfil is Perfil.ADMIN else self.inatividade_operador


class Sessao(Base):
    """Sessão aberta por login. O banco guarda só o hash do token, que vai no cookie (RN-54)."""

    __tablename__ = "sessao"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("estabelecimento.id"))
    usuario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("usuario.id"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Renovado a cada uso: a expiração é por inatividade, não por tempo desde o login (RN-36).
    ultimo_uso_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @classmethod
    def abrir(
        cls, *, estabelecimento_id: int, usuario_id: int, token_hash: str, agora: datetime
    ) -> Sessao:
        exigir_instante_com_fuso(agora)
        return cls(
            estabelecimento_id=estabelecimento_id,
            usuario_id=usuario_id,
            token_hash=token_hash,
            criada_em=agora,
            ultimo_uso_em=agora,
            encerrada_em=None,
        )

    def aceita(self, agora: datetime, usuario: Usuario, politica: PoliticaDeSessao) -> bool:
        """Recusa sessão encerrada, de conta desativada ou parada além do limite do perfil."""
        exigir_instante_com_fuso(agora)
        if self.encerrada_em is not None or not usuario.ativo:
            return False
        return agora < self.ultimo_uso_em + politica.inatividade_para(usuario.perfil)

    def renovar(self, agora: datetime) -> None:
        """Registra um uso: a sessão volta a contar o limite de inatividade (RN-36)."""
        exigir_instante_com_fuso(agora)
        self.ultimo_uso_em = agora

    def encerrar(self, agora: datetime) -> None:
        """Encerra a sessão; encerrar de novo não muda o instante original (RN-54)."""
        exigir_instante_com_fuso(agora)
        if self.encerrada_em is None:
            self.encerrada_em = agora


# Login único no estabelecimento, sem diferenciar maiúsculas (RN-60). Índice sobre expressão:
# fica depois da classe porque precisa referenciar a coluna, não o nome dela.
Index(
    "uq_usuario_estabelecimento_id_login",
    Usuario.estabelecimento_id,
    func.lower(Usuario.login),
    unique=True,
)
