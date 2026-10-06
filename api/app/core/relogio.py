"""Relógio do servidor: a única fonte do instante (ADR-005, RN-17).

O relógio do dispositivo nunca é usado. Contrato por `Protocol` porque há segunda
implementação: nos testes, um relógio fixo entra por `app.dependency_overrides` (ADR-009).
"""

from datetime import UTC, datetime
from typing import Protocol


class Relogio(Protocol):
    def agora(self) -> datetime:
        """Instante atual, com fuso UTC."""
        ...


class RelogioDoServidor:
    def agora(self) -> datetime:
        return datetime.now(UTC)


def obter_relogio() -> Relogio:
    """Dependência do FastAPI: o relógio do servidor."""
    return RelogioDoServidor()
