"""Autenticação por login e senha: confere e abre a sessão (RN-38, RN-45, ADR-006).

Conta inexistente, senha errada e conta desativada seguem o mesmo caminho e recebem a mesma
recusa. Quando a conta não existe, a senha é conferida contra um hash de referência, para o
tempo de resposta não revelar se o login existe. Logs trazem só o id da conta, nunca senha,
hash ou token (RN-45).
"""

import logging

from app.core.relogio import Relogio
from app.identidade.modelos import PoliticaDeBloqueio
from app.identidade.repositorio import RepositorioUsuarios
from app.identidade.senha import conferir, gerar_hash
from app.identidade.servico_sessao import ServicoSessao, UsuarioAutenticado

logger = logging.getLogger("app.identidade")
MENSAGEM_RECUSA = "Usuário ou senha inválidos."
_hash_de_referencia: str | None = None


async def _hash_sem_conta() -> str:
    global _hash_de_referencia
    if _hash_de_referencia is None:
        _hash_de_referencia = await gerar_hash("senha-de-referencia-sem-conta")
    return _hash_de_referencia


class ServicoAutenticacao:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        sessoes: ServicoSessao,
        politica: PoliticaDeBloqueio,
        relogio: Relogio,
    ) -> None:
        self._usuarios = usuarios
        self._sessoes = sessoes
        self._politica = politica
        self._relogio = relogio

    async def entrar(self, login: str, senha: str) -> tuple[str, UsuarioAutenticado] | None:
        """Devolve o token e o usuário, ou None quando recusa.

        A recusa é `None`, e não exceção, de propósito: a falha de senha precisa ser gravada na
        conta, e uma exceção desfaria a transação antes do commit (`obter_sessao`).
        Conta bloqueada ou desativada confere a senha mesmo assim, para o tempo de resposta não
        revelar o estado; a falha só conta quando a conta está liberada e ativa (RN-37, RN-38).
        """
        agora = self._relogio.agora()
        usuario = await self._usuarios.buscar_por_login_para_atualizar(login)
        if usuario is None:
            await conferir(senha, await _hash_sem_conta())
            logger.info("login recusado")
            return None
        senha_confere = await conferir(senha, usuario.senha_hash)
        if usuario.esta_bloqueado(agora) or not usuario.ativo:
            logger.info("login recusado", extra={"usuario_id": usuario.id})
            return None
        if not senha_confere:
            usuario.registrar_falha_login(agora, self._politica)
            logger.info("login recusado", extra={"usuario_id": usuario.id})
            return None
        usuario.registrar_login_ok()
        token = await self._sessoes.abrir(usuario)
        logger.info("login aceito", extra={"usuario_id": usuario.id})
        return token, UsuarioAutenticado.de_usuario(usuario)
