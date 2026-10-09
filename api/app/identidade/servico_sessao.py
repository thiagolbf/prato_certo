"""Sessão no servidor: abre, valida, renova e encerra (RN-36, RN-39, RN-54, ADR-006).

O service só orquestra: a expiração mora em `Sessao.aceita` e em `PoliticaDeSessao`. O token
sai aqui uma única vez, para o cookie; o banco guarda só o hash dele.
"""

import hashlib
import secrets
from dataclasses import dataclass

from app.core.excecoes import NaoAutenticado
from app.core.relogio import Relogio
from app.identidade.modelos import Perfil, PoliticaDeSessao, Sessao, Usuario
from app.identidade.repositorio import RepositorioSessoes, RepositorioUsuarios

MENSAGEM_NAO_AUTENTICADO = "Sessão inválida ou expirada. Entre novamente."


@dataclass(frozen=True)
class UsuarioAutenticado:
    """Leitura imutável do usuário da sessão: é o que os outros módulos recebem (ADR-009)."""

    id: int
    estabelecimento_id: int
    nome: str
    login: str
    perfil: Perfil

    @classmethod
    def de_usuario(cls, usuario: Usuario) -> "UsuarioAutenticado":
        return cls(
            id=usuario.id,
            estabelecimento_id=usuario.estabelecimento_id,
            nome=usuario.nome,
            login=usuario.login,
            perfil=usuario.perfil,
        )


def hash_do_token(token: str) -> str:
    # Token com 256 bits de entropia: hash rápido basta. Bcrypt é para senha, que é curta.
    return hashlib.sha256(token.encode()).hexdigest()


class ServicoSessao:
    def __init__(
        self,
        sessoes: RepositorioSessoes,
        usuarios: RepositorioUsuarios,
        politica: PoliticaDeSessao,
        relogio: Relogio,
    ) -> None:
        self._sessoes = sessoes
        self._usuarios = usuarios
        self._politica = politica
        self._relogio = relogio

    async def abrir(self, usuario: Usuario) -> str:
        """Abre uma sessão para o usuário e devolve o token, que só existe em claro aqui."""
        token = secrets.token_urlsafe(32)
        self._sessoes.adicionar(
            Sessao.abrir(
                estabelecimento_id=usuario.estabelecimento_id,
                usuario_id=usuario.id,
                token_hash=hash_do_token(token),
                agora=self._relogio.agora(),
            )
        )
        return token

    async def validar(self, token: str) -> UsuarioAutenticado:
        """Recusa a sessão inválida; a válida conta como uso e fica renovada (RN-36)."""
        sessao = await self._sessoes.buscar_por_token_hash(hash_do_token(token))
        if sessao is None:
            raise NaoAutenticado(MENSAGEM_NAO_AUTENTICADO)
        usuario = await self._usuarios.buscar_por_id(sessao.usuario_id)
        agora = self._relogio.agora()
        if usuario is None or not sessao.aceita(agora, usuario, self._politica):
            raise NaoAutenticado(MENSAGEM_NAO_AUTENTICADO)
        sessao.renovar(agora)
        return UsuarioAutenticado.de_usuario(usuario)

    async def encerrar(self, token: str) -> None:
        """Encerra a sessão do token. Token desconhecido não faz nada (RN-54)."""
        sessao = await self._sessoes.buscar_por_token_hash(hash_do_token(token))
        if sessao is not None:
            sessao.encerrar(self._relogio.agora())

    async def encerrar_outras_do_usuario(self, usuario_id: int, token_atual: str) -> None:
        """Encerra as sessões do usuário, menos a do token atual (RN-53, troca de senha)."""
        agora = self._relogio.agora()
        atual = hash_do_token(token_atual)
        for sessao in await self._sessoes.abertas_do_usuario(usuario_id):
            if sessao.token_hash != atual:
                sessao.encerrar(agora)

    async def encerrar_todas_do_usuario(self, usuario_id: int) -> None:
        """Encerra todas as sessões abertas do usuário (RN-53: recuperação do ADMIN)."""
        agora = self._relogio.agora()
        for sessao in await self._sessoes.abertas_do_usuario(usuario_id):
            sessao.encerrar(agora)
