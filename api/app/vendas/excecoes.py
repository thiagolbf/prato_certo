"""Exceções de vendas: subclasses das bases de `core`, sem conhecer HTTP (ADR-009)."""

from app.core.excecoes import Conflito, RegraViolada


class QuantidadeForaDoLimite(RegraViolada):
    """A quantidade de um lançamento vai de 1 a 20 (RN-14)."""


class VendaJaCancelada(Conflito):
    """A venda já foi cancelada; cancelar de novo não muda nada."""


class MotivoObrigatorio(RegraViolada):
    """Cancelar exige um motivo escrito."""
