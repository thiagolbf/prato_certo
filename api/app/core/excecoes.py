"""Exceções de domínio: levantadas pelas entidades, sem conhecer HTTP (ADR-009, item 7).

Cada módulo cria as suas como subclasses de uma das bases abaixo (por exemplo,
`VendaJaCancelada(Conflito)`). A tradução para o status HTTP acontece num único handler,
registrado em `app/main.py`. A mensagem é de negócio e vai ao cliente como está: nunca
colocar nela SQL, caminho de arquivo ou dado de outro estabelecimento (RN-48).
"""


class ErroDeDominio(Exception):
    """Base de todo erro de regra. Levantada direto, sem uma das bases, vira erro interno."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class NaoEncontrado(ErroDeDominio):
    """O recurso não existe, ou não pertence ao estabelecimento de quem pede."""


class Conflito(ErroDeDominio):
    """A operação colide com o estado atual: nome repetido, venda já cancelada."""


class RegraViolada(ErroDeDominio):
    """O pedido é bem formado, mas uma regra de negócio o recusa."""


class NaoAutenticado(ErroDeDominio):
    """Sem sessão válida, ou credenciais recusadas."""


class SemPermissao(ErroDeDominio):
    """Autenticado, mas o perfil não pode fazer isso."""
