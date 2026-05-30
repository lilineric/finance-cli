import json

from typer.testing import CliRunner

from finance_cli.cli import app
from finance_cli.db import DailyMetric, SQLiteApiError
from finance_cli.service import MetricQueryResult, MetricRangeQueryResult
from finance_cli.sources import DataSourceError


runner = CliRunner()


def test_cli_help_shows_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pe" in result.output
    assert "dividend-yield" in result.output
    assert "pb" in result.output
    assert "fund-nav" in result.output
    assert "cn10y-yield" in result.output
    assert "gold" in result.output
    assert "sync" in result.output


def test_pe_command_outputs_json(monkeypatch, tmp_path):
    def query(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        years,
        fetch_missing,
        ensure_lookback_coverage=False,
        minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
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
    seen = {}

    def query(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        years,
        fetch_missing,
        ensure_lookback_coverage=False,
        minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
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


def test_pe_command_accepts_ndx(monkeypatch, tmp_path):
    seen = {}

    def query(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        years,
        fetch_missing,
        ensure_lookback_coverage=False,
        minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
        seen["code"] = code
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-04-17",
            "2020-01-02",
            29.1,
            42.8,
            2000,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["pe", "--code", "NDX", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "NDX"


def test_pe_command_accepts_vn30(monkeypatch, tmp_path):
    seen = {}

    def query(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        years,
        fetch_missing,
        ensure_lookback_coverage=False,
        minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
        seen["code"] = code
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-01",
            "2016-03-01",
            16.1419,
            40.0,
            111,
            "worldperatio",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["pe", "--code", "vn30", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "VN30"


def test_pe_command_accepts_h_prefixed_csindex_code(monkeypatch, tmp_path):
    seen = {}

    def query(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        years,
        fetch_missing,
        ensure_lookback_coverage=False,
        minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
        seen["code"] = code
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-22",
            "2020-01-02",
            7.82,
            42.8,
            2000,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["pe", "--code", "h30269", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "H30269"


def test_pe_command_accepts_china_semiconductor_code(monkeypatch, tmp_path):
    seen = {}

    def query(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        years,
        fetch_missing,
        ensure_lookback_coverage=False,
        minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
        seen["code"] = code
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-22",
            "2020-01-02",
            114.73,
            80.0,
            2000,
            "akshare",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["pe", "--code", "990001", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "990001"


def test_gold_command_outputs_text(monkeypatch, tmp_path):
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


def test_fund_nav_command_outputs_unit_nav_json(monkeypatch, tmp_path):
    seen = {}

    def query_value(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        fetch_missing,
    ):
        seen["asset_type"] = asset_type
        seen["code"] = code
        seen["metric"] = metric
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-22",
            None,
            1.2456,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(
        app,
        ["fund-nav", "--code", "017763", "--date", "2026-05-23", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "fund", "code": "017763", "metric": "unit_nav"}
    payload = json.loads(result.output)
    assert payload["asset_type"] == "fund"
    assert payload["code"] == "017763"
    assert payload["metric"] == "unit_nav"
    assert payload["requested_date"] == "2026-05-23"
    assert payload["actual_date"] == "2026-05-22"
    assert payload["value"] == 1.2456
    assert "percentile" not in payload
    assert "lookback_years" not in payload


def test_fund_nav_command_supports_accumulated_nav(monkeypatch, tmp_path):
    seen = {}

    def query_value(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        fetch_missing,
    ):
        seen["metric"] = metric
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-22",
            None,
            1.9876,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(
        app,
        ["fund-nav", "--code", "017763", "--nav-type", "accumulated"],
    )

    assert result.exit_code == 0
    assert seen["metric"] == "accumulated_nav"
    assert "累计净值: 1.9876" in result.output


def test_fund_nav_help_describes_nav_type_values():
    result = runner.invoke(app, ["fund-nav", "--help"])

    assert result.exit_code == 0
    assert "--nav-type" in result.output
    assert "unit" in result.output
    assert "accumulated" in result.output


def test_fund_nav_command_rejects_invalid_code(monkeypatch, tmp_path):
    result = runner.invoke(app, ["fund-nav", "--code", "ABCDEF"])

    assert result.exit_code != 0
    assert "Invalid fund code" in result.output


def test_fund_nav_command_rejects_invalid_nav_type(monkeypatch, tmp_path):
    result = runner.invoke(app, ["fund-nav", "--code", "017763", "--nav-type", "bad"])

    assert result.exit_code != 0
    assert "bad" in result.output


def test_dividend_yield_command_accepts_h_prefixed_csindex_code(monkeypatch, tmp_path):
    seen = {}

    def query_value(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        fetch_missing,
    ):
        seen["code"] = code
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-22",
            None,
            4.82,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["dividend-yield", "--code", "h30269", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "H30269"


def test_dividend_yield_command_rejects_years(monkeypatch, tmp_path):
    result = runner.invoke(app, ["dividend-yield", "--code", "000300", "--years", "10"])

    assert result.exit_code != 0


def test_dividend_yield_command_still_rejects_ndx(monkeypatch, tmp_path):
    result = runner.invoke(app, ["dividend-yield", "--code", "NDX"])

    assert result.exit_code != 0
    assert "Invalid index code: NDX" in result.output


def test_pb_command_outputs_text(monkeypatch, tmp_path):
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


def test_pb_command_without_category_queries_index_pb(monkeypatch, tmp_path):
    seen = {}

    def query_value(
        self,
        asset_type,
        code,
        metric,
        requested_date,
        fetch_missing,
        refresh_stale=True,
    ):
        seen["asset_type"] = asset_type
        seen["code"] = code
        seen["refresh_stale"] = refresh_stale
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-05-22",
            None,
            2.23,
            None,
            None,
            "etf.run",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["pb", "--code", "930707", "--date", "2026-05-23"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "index", "code": "930707", "refresh_stale": True}
    assert "PB: 2.23" in result.output


def test_pb_command_rejects_years(monkeypatch, tmp_path):
    result = runner.invoke(app, ["pb", "--code", "801010", "--category", "一级行业", "--years", "10"])

    assert result.exit_code != 0


def test_pb_command_reports_missing_sw_code(monkeypatch, tmp_path):
    def query_value(self, asset_type, code, metric, requested_date, fetch_missing):
        raise DataSourceError("No PB data found for SW index 000300 in 一级行业")

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["pb", "--code", "000300", "--category", "一级行业"])

    assert result.exit_code != 0
    assert "No PB data found for SW index 000300 in 一级行业" in result.output
    assert "发布日期" not in result.output


def test_cn10y_yield_command_outputs_json(monkeypatch, tmp_path):
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
    def replace_sync(self, asset_type, code, metric, fetch_rows):
        return 3

    monkeypatch.setattr("finance_cli.service.MetricsService.replace_sync", replace_sync)

    result = runner.invoke(app, ["sync", "pe", "--code", "000300"])

    assert result.exit_code == 0
    assert "同步 3 条记录" in result.output


def test_sync_pe_accepts_ndx(monkeypatch, tmp_path):
    seen = {}

    def replace_sync(self, asset_type, code, metric, fetch_rows):
        rows = list(fetch_rows())
        seen["asset_type"] = asset_type
        seen["sync_code"] = code
        seen["metric"] = metric
        seen["rows"] = rows
        return 3

    def fetch_index_pe_rows(code):
        seen["code"] = code
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.replace_sync", replace_sync)
    monkeypatch.setattr("finance_cli.cli.fetch_index_pe_rows", fetch_index_pe_rows)

    result = runner.invoke(app, ["sync", "pe", "--code", "NDX"])

    assert result.exit_code == 0
    assert seen["asset_type"] == "index"
    assert seen["sync_code"] == "NDX"
    assert seen["metric"] == "rolling_pe"
    assert seen["code"] == "NDX"
    assert seen["rows"] == []
    assert "同步 3 条记录" in result.output


def test_sync_pe_uses_replace_sync_for_csi_codes(monkeypatch, tmp_path):
    """After switching to Danjuan, all PE syncs use replace_sync for clean data."""
    seen = {}

    def replace_sync(self, asset_type, code, metric, fetch_rows):
        rows = list(fetch_rows())
        seen["asset_type"] = asset_type
        seen["sync_code"] = code
        seen["metric"] = metric
        seen["rows"] = rows
        return 2

    def fetch_index_pe_rows(code):
        seen["code"] = code
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.replace_sync", replace_sync)
    monkeypatch.setattr("finance_cli.cli.fetch_index_pe_rows", fetch_index_pe_rows)

    result = runner.invoke(app, ["sync", "pe", "--code", "000300"])

    assert result.exit_code == 0
    assert seen["asset_type"] == "index"
    assert seen["sync_code"] == "000300"
    assert seen["metric"] == "rolling_pe"
    assert seen["code"] == "000300"
    assert seen["rows"] == []
    assert "同步 2 条记录" in result.output


def test_sync_gold_outputs_inserted_count(monkeypatch, tmp_path):
    def sync(self, fetch_rows):
        return 4

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "gold"])

    assert result.exit_code == 0
    assert "同步 4 条记录" in result.output


def test_sync_new_metrics_output_inserted_count(monkeypatch, tmp_path):
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
    result = runner.invoke(app, ["pb", "--code", "801010", "--category", "错误分类"])

    assert result.exit_code != 0
    assert "category" in result.output


def test_cli_reports_data_source_errors(monkeypatch, tmp_path):
    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        raise DataSourceError("source failed")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold"])

    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)
    assert "source failed" in result.output


def test_cli_reports_data_source_errors_as_json_when_requested(monkeypatch, tmp_path):
    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        raise DataSourceError("source failed")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {"error": {"code": "runtime_error", "message": "source failed"}}
    assert "╭─ Error" not in result.output


def test_cli_reports_sqlite_api_errors(monkeypatch, tmp_path):
    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        raise SQLiteApiError(500, "sqlite_error", "database is locked")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold"])

    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)
    assert "database is locked" in result.output


def test_cli_reports_sqlite_api_errors_as_json_when_requested(monkeypatch, tmp_path):
    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        raise SQLiteApiError(500, "sqlite_error", "database is locked")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "sqlite_api_error"
    assert "database is locked" in payload["error"]["message"]
    assert "╭─ Error" not in result.output


def test_cli_reports_no_data_errors_as_json_when_requested(monkeypatch, tmp_path):
    def query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        raise ValueError("No data available for gold AU9999 close on or before 2026-05-24")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "runtime_error",
            "message": "No data available for gold AU9999 close on or before 2026-05-24",
        }
    }
    assert "╭─ Error" not in result.output


def test_cli_reports_validation_errors(monkeypatch, tmp_path):
    result = runner.invoke(app, ["gold", "--years", "11"])

    assert result.exit_code != 0
    assert "between 1 and 10" in result.output


def test_cli_reports_validation_errors_as_json_when_requested(monkeypatch, tmp_path):
    result = runner.invoke(app, ["gold", "--years", "11", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {"error": {"code": "invalid_parameter", "message": "Years must be between 1 and 10"}}
    assert "╭─ Error" not in result.output


def test_cli_reports_parameter_parse_errors_as_json_when_requested(monkeypatch, tmp_path):
    result = runner.invoke(app, ["fund-nav", "--code", "017763", "--nav-type", "bad", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "invalid_parameter"
    assert "bad" in payload["error"]["message"]
    assert "╭─ Error" not in result.output


def test_cli_reports_invalid_code_as_json_when_requested(monkeypatch, tmp_path):
    result = runner.invoke(app, ["pb", "--code", "bad", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "PB without --category currently supports CSI 9xxxxx index codes only: bad",
        }
    }
    assert "╭─ Error" not in result.output


def test_pe_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update(
            {
                "asset_type": asset_type,
                "code": code,
                "metric": metric,
                "requested_from": requested_from,
                "requested_to": requested_to,
            }
        )
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-01-02", 12.3, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["pe", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {
        "asset_type": "index",
        "code": "000300",
        "metric": "rolling_pe",
        "requested_from": "2026-01-01",
        "requested_to": "2026-05-01",
    }
    payload = json.loads(result.output)
    assert payload["actual_start_date"] == "2026-01-02"
    assert payload["data"] == [{"date": "2026-01-02", "value": 12.3, "source": "akshare"}]
    assert "percentile" not in payload


def test_gold_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 540.0, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["gold", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "gold", "code": "AU9999", "metric": "close"}
    assert json.loads(result.output)["metric"] == "close"


def test_cn10y_yield_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.7, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["cn10y-yield", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "bond", "code": "CN10Y", "metric": "yield"}
    assert json.loads(result.output)["metric"] == "yield"


def test_dividend_yield_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 2.3, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["dividend-yield", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "index", "code": "000300", "metric": "dividend_yield"}
    assert json.loads(result.output)["metric"] == "dividend_yield"


def test_pb_command_without_category_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 2.23, "etf.run")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["pb", "--code", "930707", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "index", "code": "930707", "metric": "pb"}
    assert json.loads(result.output)["data"][0]["source"] == "etf.run"


def test_pb_command_with_category_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.8, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["pb", "--code", "801010", "--category", "一级行业", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "sw_index:一级行业", "code": "801010", "metric": "pb"}


def test_fund_nav_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.2456, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["fund-nav", "--code", "017763", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "fund", "code": "017763", "metric": "unit_nav"}


def test_fund_nav_command_outputs_accumulated_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.9876, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        [
            "fund-nav",
            "--code",
            "017763",
            "--nav-type",
            "accumulated",
            "--from",
            "2026-01-01",
            "--to",
            "2026-05-01",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "fund", "code": "017763", "metric": "accumulated_nav"}


def test_range_mode_requires_from_and_to(monkeypatch, tmp_path):
    result = runner.invoke(app, ["gold", "--from", "2026-01-01", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "--from and --to must be supplied together",
        }
    }


def test_range_mode_rejects_explicit_date(monkeypatch, tmp_path):
    result = runner.invoke(
        app,
        ["gold", "--from", "2026-01-01", "--to", "2026-05-01", "--date", "2026-04-20", "--json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "--date cannot be used with --from/--to",
        }
    }


def test_range_mode_rejects_explicit_years(monkeypatch, tmp_path):
    result = runner.invoke(
        app,
        ["pe", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--years", "5", "--json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "--years cannot be used with --from/--to",
        }
    }


def test_range_mode_rejects_from_after_to(monkeypatch, tmp_path):
    result = runner.invoke(
        app,
        ["gold", "--from", "2026-05-01", "--to", "2026-01-01", "--json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "from date must be on or before to date",
        }
    }


# ── M2 / Gold USD / Gold-M2-Ratio CLI tests ──


def test_m2_command_outputs_json(monkeypatch):
    def query_value(self, asset_type, code, metric, requested_date, fetch_missing):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-01", None, 21500.5, None, None, "fed", None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["m2", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["asset_type"] == "macro"
    assert payload["code"] == "M2SL"
    assert payload["metric"] == "money_supply"
    assert payload["value"] == 21500.5
    assert "percentile" not in payload
    assert "lookback_years" not in payload


def test_m2_command_outputs_text(monkeypatch):
    def query_value(self, asset_type, code, metric, requested_date, fetch_missing):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-01", None, 21500.5, None, None, "fed", None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["m2"])

    assert result.exit_code == 0
    assert "宏观: M2SL" in result.output
    assert "M2货币供应量(十亿美元): 21500.5" in result.output
    assert "历史百分位" not in result.output


def test_gold_usd_command_outputs_json(monkeypatch):
    def query_value(self, asset_type, code, metric, requested_date, fetch_missing):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-20", None, 3200.0, None, None, "akshare", None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["gold-usd", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["asset_type"] == "gold"
    assert payload["code"] == "XAUUSD"
    assert payload["metric"] == "close"
    assert payload["value"] == 3200.0
    assert "percentile" not in payload


def test_gold_m2_ratio_command_outputs_json(monkeypatch):
    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-20", "2021-01-02", 118.5, 45.0, 1500,
            "fed", years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold-m2-ratio", "--years", "5", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["asset_type"] == "macro"
    assert payload["code"] == "GOLD_M2"
    assert payload["metric"] == "ratio"
    assert payload["value"] == 118.5
    assert payload["percentile"] == 45.0
    assert payload["lookback_years"] == 5


def test_gold_m2_ratio_command_outputs_text(monkeypatch):
    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-20", "2021-01-02", 118.5, 45.0, 1500,
            "fed", years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["gold-m2-ratio", "--years", "5"])

    assert result.exit_code == 0
    assert "宏观: GOLD_M2" in result.output
    assert "黄金/M2比值: 118.5" in result.output
    assert "历史百分位: 45.0%" in result.output
    assert "回看年数: 5" in result.output


def test_m2_range_command_outputs_json(monkeypatch):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type, code, metric, requested_from, requested_to,
            "2026-01-02", "2026-04-30",
            [("2026-04-30", 21500.5, "fed")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["m2", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "macro", "code": "M2SL", "metric": "money_supply"}
    payload = json.loads(result.output)
    assert payload["data"] == [{"date": "2026-04-30", "value": 21500.5, "source": "fed"}]


def test_gold_usd_range_command_outputs_json(monkeypatch):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type, code, metric, requested_from, requested_to,
            "2026-01-02", "2026-04-30",
            [("2026-04-30", 3200.0, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["gold-usd", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "gold", "code": "XAUUSD", "metric": "close"}


def test_gold_m2_ratio_range_command_outputs_json(monkeypatch):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type, code, metric, requested_from, requested_to,
            "2026-01-02", "2026-04-30",
            [("2026-04-30", 118.5, "fed")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["gold-m2-ratio", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "macro", "code": "GOLD_M2", "metric": "ratio"}


def test_sync_m2_outputs_inserted_count(monkeypatch):
    def sync(self, fetch_rows):
        return 120

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "m2"])

    assert result.exit_code == 0
    assert "同步 120 条记录" in result.output


def test_sync_gold_usd_outputs_inserted_count(monkeypatch):
    def sync(self, fetch_rows):
        return 5000

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "gold-usd"])

    assert result.exit_code == 0
    assert "同步 5000 条记录" in result.output


def test_sync_gold_m2_ratio_outputs_inserted_count(monkeypatch):
    def sync(self, fetch_rows):
        return 4500

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "gold-m2-ratio"])

    assert result.exit_code == 0
    assert "同步 4500 条记录" in result.output


def test_cli_help_shows_new_commands(monkeypatch):
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "m2" in result.output
    assert "gold-usd" in result.output
    assert "gold-m2-ratio" in result.output
    assert "dividend-yield-spread" in result.output


def test_dividend_yield_spread_command_outputs_json(monkeypatch):
    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2020-01-02", 2.88, 35.0, 1500,
            "akshare", years,
        )

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        if metric == "dividend_yield":
            return [DailyMetric("index", code, metric, "2026-05-29", 4.5, "akshare")]
        if metric == "yield":
            return [DailyMetric("bond", "CN10Y", metric, "2026-05-29", 1.62, "akshare")]
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["dividend-yield-spread", "--code", "H30269", "--years", "5", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["asset_type"] == "spread"
    assert payload["code"] == "H30269"
    assert payload["metric"] == "dividend_yield_spread"
    assert payload["value"] == 2.88
    assert payload["percentile"] == 35.0
    assert payload["lookback_years"] == 5
    assert payload["dividend_yield"] == 4.5
    assert payload["cn10y_yield"] == 1.62


def test_dividend_yield_spread_command_outputs_text(monkeypatch):
    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2020-01-02", 2.88, 35.0, 1500,
            "akshare", years,
        )

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        if metric == "dividend_yield":
            return [DailyMetric("index", code, metric, "2026-05-29", 4.5, "akshare")]
        if metric == "yield":
            return [DailyMetric("bond", "CN10Y", metric, "2026-05-29", 1.62, "akshare")]
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["dividend-yield-spread", "--code", "H30269", "--years", "5"])

    assert result.exit_code == 0
    assert "利差: H30269" in result.output
    assert "股息率-国债收益率利差: 2.88" in result.output
    assert "历史百分位: 35.0%" in result.output
    assert "回看年数: 5" in result.output
    assert "股息率: 4.5" in result.output
    assert "10年期国债收益率: 1.62" in result.output


def test_dividend_yield_spread_command_with_lowercase_h_code(monkeypatch):
    seen_code = {}

    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        seen_code["code"] = code
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2020-01-02", 2.88, 35.0, 1500,
            "akshare", years,
        )

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["dividend-yield-spread", "--code", "h30269", "--json"])

    assert result.exit_code == 0
    assert seen_code["code"] == "H30269"
    payload = json.loads(result.output)
    assert payload["code"] == "H30269"


def test_dividend_yield_spread_range_command_outputs_json(monkeypatch):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type, code, metric, requested_from, requested_to,
            "2026-01-02", "2026-04-30",
            [("2026-04-30", 2.88, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["dividend-yield-spread", "--code", "H30269", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "spread", "code": "H30269", "metric": "dividend_yield_spread"}


def test_sync_dividend_yield_spread_outputs_inserted_count(monkeypatch):
    def sync(self, fetch_rows):
        return 2000

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "dividend-yield-spread", "--code", "000300"])

    assert result.exit_code == 0
    assert "同步 2000 条记录" in result.output
