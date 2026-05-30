import json

import pytest

from finance_cli.config import (
    DEFAULT_SQLITE_API_HOST,
    DEFAULT_SQLITE_DB,
    load_config,
)


def test_load_config_uses_defaults_when_no_file_is_configured(monkeypatch):
    monkeypatch.delenv("FINANCE_CLI_CONFIG", raising=False)

    config = load_config()

    assert config.sqlite_api_host == DEFAULT_SQLITE_API_HOST
    assert config.sqlite_db == DEFAULT_SQLITE_DB


def test_load_config_uses_environment_config_file(monkeypatch, tmp_path):
    config_path = tmp_path / "finance-cli.json"
    config_path.write_text(
        json.dumps(
            {
                "sqlite_api_host": "http://127.0.0.1:8080/",
                "sqlite_db": "finance.db",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FINANCE_CLI_CONFIG", str(config_path))

    config = load_config()

    assert config.sqlite_api_host == "http://127.0.0.1:8080"
    assert config.sqlite_db == "finance.db"


def test_load_config_reads_fred_api_key(monkeypatch, tmp_path):
    config_path = tmp_path / "finance-cli.json"
    config_path.write_text(
        json.dumps(
            {
                "sqlite_api_host": "http://127.0.0.1:8080",
                "sqlite_db": "finance.db",
                "fred_api_key": "test-fred-key-123",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FINANCE_CLI_CONFIG", str(config_path))

    config = load_config()

    assert config.fred_api_key == "test-fred-key-123"


def test_load_config_defaults_fred_api_key_to_empty_when_not_present(monkeypatch, tmp_path):
    config_path = tmp_path / "finance-cli.json"
    config_path.write_text(
        json.dumps(
            {
                "sqlite_api_host": "http://127.0.0.1:8080",
                "sqlite_db": "finance.db",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FINANCE_CLI_CONFIG", str(config_path))

    config = load_config()

    assert config.fred_api_key == ""


def test_load_config_rejects_empty_values(monkeypatch, tmp_path):
    config_path = tmp_path / "finance-cli.json"
    config_path.write_text(
        json.dumps({"sqlite_api_host": " ", "sqlite_db": "finance.db"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("FINANCE_CLI_CONFIG", str(config_path))

    with pytest.raises(ValueError, match="sqlite_api_host"):
        load_config()
