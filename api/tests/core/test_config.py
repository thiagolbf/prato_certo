from pathlib import Path

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
        Configuracao(_env_file=None)  # sem o .env local, só o que está no código

    campos_faltando = {e["loc"][0] for e in erro.value.errors()}
    assert campos_faltando == {"database_url", "segredo_sessao"}


def test_le_o_arquivo_env_e_a_variavel_de_ambiente_tem_prioridade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    arquivo_env = tmp_path / ".env"
    arquivo_env.write_text(
        "DATABASE_URL=postgresql+asyncpg://u:s@localhost:5432/pf\n"
        "SEGREDO_SESSAO=do-arquivo\n"
        "POSTGRES_USER=ignorada\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SEGREDO_SESSAO", "do-ambiente")

    config = Configuracao(_env_file=arquivo_env)

    assert config.database_url.get_secret_value() == "postgresql+asyncpg://u:s@localhost:5432/pf"
    assert config.segredo_sessao.get_secret_value() == "do-ambiente"


def test_segredos_nao_aparecem_na_representacao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:senha-secreta@db:5432/pf")
    monkeypatch.setenv("SEGREDO_SESSAO", "segredo-secreto")

    representacao = repr(Configuracao())

    assert "senha-secreta" not in representacao
    assert "segredo-secreto" not in representacao
