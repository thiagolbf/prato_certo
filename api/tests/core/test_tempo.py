"""Relógio do servidor, dia e mês operacionais (ADR-005, RN-17, RN-27, RN-55).

Os cenários CA-19 e CA-20 só ficam verdes na T-31; aqui a fronteira do dia é provada em unidade.
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.core.relogio import RelogioDoServidor, obter_relogio
from app.core.tempo import FUSO, NOME_FUSO, DiaOperacional, MesOperacional


class RelogioFixo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def agora(self) -> datetime:
        return self.instante


def test_fuso_aparece_em_uma_unica_constante() -> None:
    """O fuso é constante única da aplicação, nunca repetido em consulta (ADR-005)."""
    pasta_app = Path(__file__).resolve().parents[2] / "app"
    ocorrencias = [
        (arquivo.name, linha)
        for arquivo in pasta_app.rglob("*.py")
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if "America/Sao_Paulo" in linha
    ]

    assert ocorrencias == [("tempo.py", 'NOME_FUSO = "America/Sao_Paulo"')]
    assert NOME_FUSO == "America/Sao_Paulo"


def test_relogio_do_servidor_devolve_instante_em_utc() -> None:
    agora = RelogioDoServidor().agora()

    assert agora.tzinfo is UTC
    assert abs(datetime.now(UTC) - agora) < timedelta(seconds=5)


def test_dependencia_entrega_o_relogio_do_servidor() -> None:
    assert isinstance(obter_relogio(), RelogioDoServidor)


def _instante_utc_da_hora_local(*campos: int) -> datetime:
    """Hora de São Paulo, como o PRD escreve o cenário, convertida para o instante UTC gravado."""
    return datetime(*campos, tzinfo=FUSO).astimezone(UTC)


def test_instante_2359_pertence_ao_dia_corrente() -> None:
    instante = _instante_utc_da_hora_local(2026, 9, 22, 23, 59)

    assert DiaOperacional.do_instante(instante) == DiaOperacional(date(2026, 9, 22))


def test_instante_0001_pertence_ao_dia_seguinte() -> None:
    instante = _instante_utc_da_hora_local(2026, 9, 23, 0, 1)

    assert DiaOperacional.do_instante(instante) == DiaOperacional(date(2026, 9, 23))


def test_0259_utc_pertence_ao_dia_anterior() -> None:
    """A data UTC já virou, mas o dia operacional ainda não (ADR-009, consequências)."""
    instante = datetime(2026, 9, 23, 2, 59, 59, tzinfo=UTC)

    assert instante.date() == date(2026, 9, 23)
    assert DiaOperacional.do_instante(instante).data == date(2026, 9, 22)


def test_dia_operacional_recusa_instante_no_construtor() -> None:
    """`datetime` é subclasse de `date`: aceito, viraria a data UTC, o dia errado (ADR-005)."""
    instante = datetime(2026, 9, 23, 2, 59, tzinfo=UTC)

    with pytest.raises(TypeError, match="do_instante"):
        DiaOperacional(instante)


def test_dia_operacional_recusa_valor_que_nao_e_data() -> None:
    with pytest.raises(TypeError, match="date"):
        DiaOperacional("2026-09-22")  # type: ignore[arg-type]


def test_instante_sem_fuso_e_recusado() -> None:
    with pytest.raises(ValueError, match="fuso"):
        DiaOperacional.do_instante(datetime(2026, 9, 22, 23, 59))


def test_intervalo_do_dia_cobre_exatamente_24_horas() -> None:
    dia = DiaOperacional(date(2026, 9, 22))

    inicio, fim = dia.intervalo_utc()

    assert inicio == datetime(2026, 9, 22, 3, 0, tzinfo=UTC)
    assert fim == datetime(2026, 9, 23, 3, 0, tzinfo=UTC)
    assert fim - inicio == timedelta(hours=24)
    assert inicio.tzinfo is UTC and fim.tzinfo is UTC


def test_intervalo_do_dia_e_fechado_no_inicio_e_aberto_no_fim() -> None:
    inicio, fim = DiaOperacional(date(2026, 9, 22)).intervalo_utc()

    assert DiaOperacional.do_instante(inicio).data == date(2026, 9, 22)
    assert DiaOperacional.do_instante(fim - timedelta(microseconds=1)).data == date(2026, 9, 22)
    assert DiaOperacional.do_instante(fim).data == date(2026, 9, 23)


def test_dia_corrente_vem_do_relogio_do_servidor() -> None:
    relogio = RelogioFixo(datetime(2026, 9, 23, 2, 59, tzinfo=UTC))

    assert DiaOperacional.corrente(relogio) == DiaOperacional(date(2026, 9, 22))


def test_intervalo_do_mes_de_agosto() -> None:
    inicio, fim = MesOperacional(2026, 8).intervalo_utc()

    assert inicio == datetime(2026, 8, 1, 3, 0, tzinfo=UTC)
    assert fim == datetime(2026, 9, 1, 3, 0, tzinfo=UTC)
    assert fim - inicio == timedelta(days=31)


def test_ultimo_instante_de_31_08_pertence_a_agosto_e_01_09_nao() -> None:
    _, fim = MesOperacional(2026, 8).intervalo_utc()

    assert MesOperacional.do_instante(fim - timedelta(microseconds=1)) == MesOperacional(2026, 8)
    assert MesOperacional.do_instante(fim) == MesOperacional(2026, 9)


def test_intervalo_do_mes_de_dezembro_vira_o_ano() -> None:
    inicio, fim = MesOperacional(2026, 12).intervalo_utc()

    assert inicio == datetime(2026, 12, 1, 3, 0, tzinfo=UTC)
    assert fim == datetime(2027, 1, 1, 3, 0, tzinfo=UTC)


def test_mes_corrente_vem_do_relogio_do_servidor() -> None:
    # 31/08 23:30 em São Paulo = 01/09 02:30 UTC.
    relogio = RelogioFixo(datetime(2026, 9, 1, 2, 30, tzinfo=UTC))

    assert MesOperacional.corrente(relogio) == MesOperacional(2026, 8)


@pytest.mark.parametrize("mes", [0, 13])
def test_mes_invalido_e_recusado(mes: int) -> None:
    with pytest.raises(ValueError, match="mês"):
        MesOperacional(2026, mes)


@pytest.mark.parametrize(("ano", "mes"), [("2026", 8), (2026, "08"), (2026, 8.0), (2026, True)])
def test_mes_operacional_recusa_ano_ou_mes_que_nao_e_inteiro(ano: object, mes: object) -> None:
    with pytest.raises(TypeError, match="inteiro"):
        MesOperacional(ano, mes)  # type: ignore[arg-type]
