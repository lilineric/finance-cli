import json

from typer.testing import CliRunner

from finance_cli.cli import app
from finance_cli.service import MetricQueryResult
from finance_cli.sources import DataSourceError


runner = CliRunner()


def test_cli_help_shows_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pe" in result.output
    assert "gold" in result.output
    assert "sync" in result.output


def test_pe_command_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            12.34,
            42.8,
            2000,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(
        app,
        ["pe", "--code", "000300", "--date", "2026-04-20", "--years", "10", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["code"] == "000300"
    assert payload["metric"] == "pe_ttm"
    assert payload["lookback_years"] == 10


def test_gold_command_outputs_text(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            535.2,
            80.0,
            2400,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold", "--date", "2026-04-20"])

    assert result.exit_code == 0
    assert "AU9999" in result.output
    assert "80.0%" in result.output
    assert "回看年数" in result.output


def test_sync_pe_outputs_inserted_count(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def sync(self, fetch_rows):
        return 3

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "pe", "--code", "000300"])

    assert result.exit_code == 0
    assert "同步 3 条记录" in result.output


def test_sync_gold_outputs_inserted_count(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def sync(self, fetch_rows):
        return 4

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "gold"])

    assert result.exit_code == 0
    assert "同步 4 条记录" in result.output


def test_cli_reports_data_source_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        raise DataSourceError("source failed")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold"])

    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)
    assert "source failed" in result.output


def test_cli_reports_validation_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    result = runner.invoke(app, ["gold", "--years", "11"])

    assert result.exit_code != 0
    assert "between 1 and 10" in result.output
