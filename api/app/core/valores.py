"""Objetos de valor imutáveis: dinheiro e gramagem (ADR-009, RN-16).

Dinheiro é sempre `Decimal` com duas casas, nunca `float`: a fração de centavo é recusada
em vez de arredondada, para que nenhuma conta perca centavos em silêncio.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

CENTAVO = Decimal("0.01")


def _exigir_inteiro(valor: object, nome: str) -> int:
    # bool é subclasse de int, mas True não é uma quantidade.
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise TypeError(f"{nome} precisa ser inteiro, recebido {type(valor).__name__}")
    return valor


@dataclass(frozen=True, order=True)
class Dinheiro:
    valor: Decimal

    def __init__(self, valor: Decimal | int | str) -> None:
        if isinstance(valor, float):
            raise TypeError("Dinheiro não aceita float; use Decimal, int ou str")
        try:
            decimal = Decimal(valor)
        except InvalidOperation as erro:
            raise ValueError(f"Valor de dinheiro inválido: {valor!r}") from erro
        if not decimal.is_finite():
            raise ValueError(f"Valor de dinheiro inválido: {valor!r}")
        centavos = decimal.quantize(CENTAVO)
        if centavos != decimal:
            raise ValueError(f"Dinheiro não tem fração de centavo: {valor!r}")
        object.__setattr__(self, "valor", centavos)

    @classmethod
    def zero(cls) -> Dinheiro:
        return cls(0)

    def __add__(self, outro: Dinheiro) -> Dinheiro:
        if not isinstance(outro, Dinheiro):
            return NotImplemented
        return Dinheiro(self.valor + outro.valor)

    def __mul__(self, quantidade: int) -> Dinheiro:
        return Dinheiro(self.valor * _exigir_inteiro(quantidade, "quantidade"))

    __rmul__ = __mul__

    def __str__(self) -> str:
        return str(self.valor)


@dataclass(frozen=True, order=True)
class Gramagem:
    """Inteiro positivo, em gramas."""

    gramas: int

    def __post_init__(self) -> None:
        if _exigir_inteiro(self.gramas, "gramagem") <= 0:
            raise ValueError(f"gramagem precisa ser positiva, recebido {self.gramas}")

    def __mul__(self, quantidade: int) -> Gramagem:
        return Gramagem(self.gramas * _exigir_inteiro(quantidade, "quantidade"))

    __rmul__ = __mul__
