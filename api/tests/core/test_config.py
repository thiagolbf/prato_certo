import pytest
from pydantic import ValidationError

from app.core.config import Configuracao


def test_configuracao_vem_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:s@db:5432/pf")
    monkeypatch.setenv("SEGREDO_SESSAO", "segredo")
    monkeypatch.setenv("PORT", "10000")

    config = Configuracao()

    assert config.port == 10000
    assert config.database_url.get_secret_value() == "postgresql+asyncpg://u:s@db:5432/pf"


def test_segredos_sao_obrigatorios_e_nao_tem_valor_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SEGREDO_SESSAO", raising=False)

    with pytest.raises(ValidationError) as erro:
        Configuracao()

    campos_faltando = {e["loc"][0] for e in erro.value.errors()}
    assert campos_faltando == {"database_url", "segredo_sessao"}


def test_segredos_nao_aparecem_na_representacao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:senha-secreta@db:5432/pf")
    monkeypatch.setenv("SEGREDO_SESSAO", "segredo-secreto")

    representacao = repr(Configuracao())

    assert "senha-secreta" not in representacao
    assert "segredo-secreto" not in representacao
