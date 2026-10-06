"""Log estruturado em JSON, com filtro de dado sensível (RN-45, RN-48).

Todo logger da aplicação é filho de `app` (`logging.getLogger("app.vendas")`, por exemplo).
O filtro troca por `[removido]` o valor de qualquer campo cujo nome indique senha, hash,
cookie, cabeçalho de autenticação, token ou corpo de requisição, em qualquer profundidade
dos dados passados em `extra`. Ele protege contra o descuido estruturado; texto montado na
mensagem não tem como ser filtrado, então dado sensível nunca entra na mensagem.
"""

import json
import logging
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TextIO

NOME_LOGGER = "app"
REMOVIDO = "[removido]"
# Comparados com o nome do campo em minúsculas: "senha_hash", "Set-Cookie", "corpo_login"...
FRAGMENTOS_SENSIVEIS = (
    "senha",
    "password",
    "hash",
    "cookie",
    "authorization",
    "token",
    "segredo",
    "secret",
    "corpo",
    "body",
)
_ATRIBUTOS_DO_REGISTRO = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
}


def _e_sensivel(chave: object) -> bool:
    if isinstance(chave, bytes):
        chave = chave.decode("latin-1")
    if not isinstance(chave, str):
        return False
    nome = chave.lower()
    return any(fragmento in nome for fragmento in FRAGMENTOS_SENSIVEIS)


def _higienizar(chave: object, valor: object) -> object:
    """Cópia de `valor` sem dado sensível; o objeto de quem chamou não é alterado."""
    if _e_sensivel(chave):
        return REMOVIDO
    if isinstance(valor, Mapping):
        return {k: _higienizar(k, v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        # Par (nome, valor), como os cabeçalhos ASGI: o nome decide sobre o valor.
        if len(valor) == 2 and isinstance(valor[0], str | bytes):
            return (valor[0], _higienizar(valor[0], valor[1]))
        return [_higienizar(None, item) for item in valor]
    return valor


def _campos_extras(registro: logging.LogRecord) -> dict[str, object]:
    return {k: v for k, v in vars(registro).items() if k not in _ATRIBUTOS_DO_REGISTRO}


class FiltroDadosSensiveis(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for chave, valor in _campos_extras(record).items():
            setattr(record, chave, _higienizar(chave, valor))
        if isinstance(record.args, Mapping):
            record.args = _higienizar(None, record.args)  # type: ignore[assignment]
        return True


class FormatadorJson(logging.Formatter):
    """Uma linha JSON por registro: instante UTC, nível, logger, mensagem e campos extras."""

    CAMPOS = frozenset({"instante", "nivel", "logger", "mensagem", "excecao"})

    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, object] = {
            "instante": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        for chave, valor in _campos_extras(record).items():
            # Extra com nome de campo do formato não o sobrescreve: vai prefixado.
            dados[f"extra_{chave}" if chave in self.CAMPOS else chave] = valor
        if record.exc_info:
            dados["excecao"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


def configurar_log(destino: TextIO | None = None) -> None:
    """Configura o logger `app`; chamar de novo substitui a configuração anterior."""
    logger = logging.getLogger(NOME_LOGGER)
    for anterior in [h for h in logger.handlers if h.name == NOME_LOGGER]:
        logger.removeHandler(anterior)
    handler = logging.StreamHandler(destino or sys.stderr)
    handler.name = NOME_LOGGER
    handler.addFilter(FiltroDadosSensiveis())
    handler.setFormatter(FormatadorJson())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Sem propagar: um handler na raiz (o do Alembic, por exemplo) gravaria sem o filtro.
    logger.propagate = False
