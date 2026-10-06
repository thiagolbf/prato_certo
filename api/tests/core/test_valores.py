"""Objetos de valor Dinheiro e Gramagem (ADR-009, RN-16)."""

from decimal import Decimal

import pytest

from app.core.valores import Dinheiro, Gramagem


def test_dinheiro_recusa_float() -> None:
    with pytest.raises(TypeError, match="float"):
        Dinheiro(18.5)  # type: ignore[arg-type]


def test_dinheiro_guarda_duas_casas() -> None:
    assert Dinheiro(Decimal("18")).valor == Decimal("18.00")
    assert Dinheiro("18.5").valor == Decimal("18.50")
    assert str(Dinheiro(22).valor) == "22.00"


def test_dinheiro_recusa_fracao_de_centavo() -> None:
    with pytest.raises(ValueError, match="centavo"):
        Dinheiro(Decimal("18.005"))


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "abc"])
def test_dinheiro_recusa_valor_que_nao_e_numero_finito(valor: str) -> None:
    with pytest.raises(ValueError):
        Dinheiro(valor)


def test_dinheiro_soma_sem_perder_centavos() -> None:
    # Em float, 0.1 + 0.2 != 0.3.
    assert Dinheiro("0.10") + Dinheiro("0.20") == Dinheiro("0.30")
    assert sum([Dinheiro("0.10")] * 10, Dinheiro.zero()) == Dinheiro("1.00")


def test_dinheiro_multiplica_por_quantidade() -> None:
    # RN-16: valor = preço unitário × quantidade.
    assert Dinheiro("18.00") * 10 == Dinheiro("180.00")
    assert 3 * Dinheiro("0.10") == Dinheiro("0.30")
    assert Dinheiro("19.99") * 20 == Dinheiro("399.80")


def test_dinheiro_recusa_multiplicar_por_nao_inteiro() -> None:
    with pytest.raises(TypeError):
        Dinheiro("18.00") * 1.5  # type: ignore[operator]
    with pytest.raises(TypeError):
        Dinheiro("18.00") * True  # type: ignore[operator]


def test_dinheiro_recusa_somar_com_outro_tipo() -> None:
    with pytest.raises(TypeError):
        Dinheiro("18.00") + Decimal("1.00")  # type: ignore[operator]


def test_dinheiro_e_comparavel_e_imutavel() -> None:
    preco = Dinheiro("18.00")

    assert Dinheiro("18.00") < Dinheiro("22.00")
    with pytest.raises(AttributeError):
        preco.valor = Decimal("1.00")  # type: ignore[misc]


def test_gramagem_guarda_inteiro_positivo_em_gramas() -> None:
    assert Gramagem(150).gramas == 150


@pytest.mark.parametrize("gramas", [0, -150])
def test_gramagem_recusa_zero_ou_negativa(gramas: int) -> None:
    with pytest.raises(ValueError, match="positiva"):
        Gramagem(gramas)


@pytest.mark.parametrize("gramas", [150.0, Decimal("150"), "150", True])
def test_gramagem_recusa_valor_que_nao_e_inteiro(gramas: object) -> None:
    with pytest.raises(TypeError, match="inteiro"):
        Gramagem(gramas)  # type: ignore[arg-type]


def test_gramagem_multiplica_por_quantidade() -> None:
    # RN-16: proteína da venda = gramagem × quantidade.
    assert Gramagem(150) * 10 == Gramagem(1500)
    assert 4 * Gramagem(150) == Gramagem(600)
