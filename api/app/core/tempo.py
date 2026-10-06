"""Dia e mês operacionais: o único lugar com o fuso do negócio (ADR-005, ADR-009, RN-27).

O instante é sempre UTC; a que dia ele pertence é interpretação feita só aqui. Consultas
filtram pelo intervalo UTC `[início, fim)`, nunca por `date(registrada_em)` no banco, que
ignoraria o fuso. SQL que precise do fuso recebe `NOME_FUSO` como parâmetro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.relogio import Relogio

NOME_FUSO = "America/Sao_Paulo"
FUSO = ZoneInfo(NOME_FUSO)


def _data_local(instante: datetime) -> date:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("Instante sem fuso: esperado um datetime em UTC (ADR-005)")
    return instante.astimezone(FUSO).date()


def _meia_noite_utc(data: date) -> datetime:
    return datetime.combine(data, time.min, tzinfo=FUSO).astimezone(UTC)


@dataclass(frozen=True, order=True)
class DiaOperacional:
    """Data civil no fuso do negócio (`NOME_FUSO`), de 00:00:00 a 23:59:59 (RN-27)."""

    data: date

    def __post_init__(self) -> None:
        # `datetime` é subclasse de `date`: aceito aqui, viraria a data UTC — o dia errado.
        if isinstance(self.data, datetime):
            raise TypeError("DiaOperacional recebe uma data; para um instante, use do_instante")
        if not isinstance(self.data, date):
            raise TypeError(f"DiaOperacional precisa de date, recebido {type(self.data).__name__}")

    @classmethod
    def do_instante(cls, instante: datetime) -> DiaOperacional:
        return cls(_data_local(instante))

    @classmethod
    def corrente(cls, relogio: Relogio) -> DiaOperacional:
        return cls.do_instante(relogio.agora())

    def intervalo_utc(self) -> tuple[datetime, datetime]:
        """Intervalo `[início, fim)` em UTC, para filtrar consultas."""
        return _meia_noite_utc(self.data), _meia_noite_utc(self.data + timedelta(days=1))


@dataclass(frozen=True, order=True)
class MesOperacional:
    """Mês civil no fuso do negócio: todos os seus dias operacionais (RN-55)."""

    ano: int
    mes: int

    def __post_init__(self) -> None:
        for nome, valor in (("ano", self.ano), ("mês", self.mes)):
            # bool é subclasse de int, mas True não é um mês.
            if not isinstance(valor, int) or isinstance(valor, bool):
                raise TypeError(f"{nome} precisa ser inteiro, recebido {type(valor).__name__}")
        if not 1 <= self.mes <= 12:
            raise ValueError(f"mês inválido: {self.mes}")

    @classmethod
    def do_instante(cls, instante: datetime) -> MesOperacional:
        data = _data_local(instante)
        return cls(data.year, data.month)

    @classmethod
    def corrente(cls, relogio: Relogio) -> MesOperacional:
        return cls.do_instante(relogio.agora())

    def intervalo_utc(self) -> tuple[datetime, datetime]:
        """Intervalo `[início, fim)` em UTC, do primeiro dia ao primeiro do mês seguinte."""
        primeiro = date(self.ano, self.mes, 1)
        seguinte = date(self.ano + 1, 1, 1) if self.mes == 12 else date(self.ano, self.mes + 1, 1)
        return _meia_noite_utc(primeiro), _meia_noite_utc(seguinte)
