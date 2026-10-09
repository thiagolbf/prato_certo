"""Usuários do estabelecimento: cadastro, lista, desativação e reativação (RN-34, RN-52, RN-60).

É o único ponto de criação de usuário. A API cria Operador por aqui, e o comando técnico cria
ADMIN pelo mesmo método, para a regra de login único valer nos dois caminhos.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.core.excecoes import Conflito, NaoEncontrado
from app.core.relogio import Relogio
from app.identidade.modelos import Perfil, Usuario
from app.identidade.repositorio import RepositorioUsuarios
from app.identidade.senha import gerar_hash
from app.identidade.servico_sessao import ServicoSessao

logger = logging.getLogger("app.identidade")
MENSAGEM_LOGIN_REPETIDO = "Já existe um usuário com esse login."


@dataclass(frozen=True)
class UsuarioLeitura:
    """Leitura imutável para a lista e as respostas de ADMIN."""

    id: int
    nome: str
    login: str
    perfil: Perfil
    ativo: bool
    bloqueado_ate: datetime | None

    @classmethod
    def de(cls, usuario: Usuario, agora: datetime) -> "UsuarioLeitura":
        # O bloqueio só é informado enquanto vale (RN-52).
        bloqueado = usuario.bloqueado_ate if usuario.esta_bloqueado(agora) else None
        return cls(
            id=usuario.id,
            nome=usuario.nome,
            login=usuario.login,
            perfil=usuario.perfil,
            ativo=usuario.ativo,
            bloqueado_ate=bloqueado,
        )


class ServicoUsuarios:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        sessoes: ServicoSessao,
        relogio: Relogio,
        estabelecimento_id: int,
    ) -> None:
        self._usuarios = usuarios
        self._sessoes = sessoes
        self._relogio = relogio
        self._estabelecimento_id = estabelecimento_id

    async def criar(self, *, nome: str, login: str, senha: str, perfil: Perfil) -> UsuarioLeitura:
        # Checagem antes do hash: login repetido não gasta bcrypt.
        if await self._usuarios.buscar_por_login(login) is not None:
            raise Conflito(MENSAGEM_LOGIN_REPETIDO)
        usuario = Usuario.criar(
            estabelecimento_id=self._estabelecimento_id,
            nome=nome,
            login=login,
            senha_hash=await gerar_hash(senha),
            perfil=perfil,
        )
        self._usuarios.adicionar(usuario)
        try:
            await self._usuarios.persistir()
        except IntegrityError as erro:
            # Corrida: outro cadastro com o mesmo login entrou entre a checagem e o insert.
            raise Conflito(MENSAGEM_LOGIN_REPETIDO) from erro
        logger.info("usuario criado", extra={"usuario_id": usuario.id, "perfil": perfil.value})
        return UsuarioLeitura.de(usuario, self._relogio.agora())

    async def listar(self) -> list[UsuarioLeitura]:
        agora = self._relogio.agora()
        return [UsuarioLeitura.de(usuario, agora) for usuario in await self._usuarios.listar()]

    async def desativar(self, usuario_id: int, por_id: int) -> UsuarioLeitura:
        usuario = await self._buscar(usuario_id)
        usuario.exigir_desativavel_por(por_id)
        usuario.desativar()
        # Quem já estava logado perde o acesso agora, não só no próximo login (RN-34).
        await self._sessoes.encerrar_todas_do_usuario(usuario.id)
        logger.info("usuario desativado", extra={"usuario_id": usuario.id, "por_id": por_id})
        return UsuarioLeitura.de(usuario, self._relogio.agora())

    async def reativar(self, usuario_id: int, por_id: int) -> UsuarioLeitura:
        usuario = await self._buscar(usuario_id)
        usuario.reativar()
        logger.info("usuario reativado", extra={"usuario_id": usuario.id, "por_id": por_id})
        return UsuarioLeitura.de(usuario, self._relogio.agora())

    async def _buscar(self, usuario_id: int) -> Usuario:
        usuario = await self._usuarios.buscar_por_id(usuario_id)
        if usuario is None:
            raise NaoEncontrado("Usuário não encontrado.")
        return usuario
