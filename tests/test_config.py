from pathlib import Path

from finance_cli.config import default_db_path, resolve_db_path


def test_default_db_path_uses_home_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("FINANCE_CLI_DB", raising=False)

    assert default_db_path() == tmp_path / ".finance-cli" / "finance.db"


def test_resolve_db_path_uses_environment_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom.db"
    monkeypatch.setenv("FINANCE_CLI_DB", str(custom))

    assert resolve_db_path() == custom
