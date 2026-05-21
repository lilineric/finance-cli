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
    assert "dividend-yield" in result.output
    assert "pb" in result.output
    assert "cn10y-yield" in result.output
    assert "gold" in result.output
    assert "sync" in result.output


def test_pe_command_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing, ensure_lookback_coverage=False):
        assert ensure_lookback_coverage is True
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            "2020-01-02",
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
    assert payload["metric"] == "rolling_pe"
    assert payload["lookback_years"] == 10
    assert payload["sample_start_date"] == "2020-01-02"


def test_pe_command_normalizes_exchange_prefixed_code(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))
    seen = {}

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing, ensure_lookback_coverage=False):
        assert ensure_lookback_coverage is True
        seen["code"] = code
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            "2020-01-02",
            12.34,
            42.8,
            2000,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["pe", "--code", "SH000300", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "000300"


def test_gold_command_outputs_text(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            "2021-03-01",
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


def test_dividend_yield_command_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query_value(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        fetch_missing,
    ):
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            None,
            3.1,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(
        app,
        ["dividend-yield", "--code", "000300", "--date", "2026-04-20", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["code"] == "000300"
    assert payload["metric"] == "dividend_yield"
    assert "percentile" not in payload
    assert "lookback_years" not in payload
    assert "sample_count" not in payload
    assert "sample_start_date" not in payload


def test_dividend_yield_command_rejects_years(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    result = runner.invoke(app, ["dividend-yield", "--code", "000300", "--years", "10"])

    assert result.exit_code != 0


def test_pb_command_outputs_text(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query_value(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        fetch_missing,
    ):
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            None,
            1.8,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(
        app,
        ["pb", "--code", "801010", "--category", "一级行业", "--date", "2026-04-20"],
    )

    assert result.exit_code == 0
    assert "801010" in result.output
    assert "PB: 1.8" in result.output
    assert "历史百分位" not in result.output
    assert "回看年数" not in result.output
    assert "样本数" not in result.output
    assert "样本起始日期" not in result.output


def test_pb_command_rejects_years(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    result = runner.invoke(app, ["pb", "--code", "801010", "--category", "一级行业", "--years", "10"])

    assert result.exit_code != 0


def test_cn10y_yield_command_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            "2020-01-02",
            1.7,
            20.0,
            2000,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["cn10y-yield", "--date", "2026-04-20", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["code"] == "CN10Y"
    assert payload["metric"] == "yield"


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


def test_sync_new_metrics_output_inserted_count(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def sync(self, fetch_rows):
        return 5

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    commands = [
        ["sync", "dividend-yield", "--code", "000300"],
        ["sync", "pb", "--code", "801010", "--category", "一级行业"],
        ["sync", "cn10y-yield"],
    ]
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0
        assert "同步 5 条记录" in result.output


def test_pb_rejects_invalid_category(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    result = runner.invoke(app, ["pb", "--code", "801010", "--category", "错误分类"])

    assert result.exit_code != 0
    assert "category" in result.output


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
