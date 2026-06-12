import json

from typer.testing import CliRunner

from finance_cli.cli import app
from finance_cli.db import DailyMetric, FundInfo, OperationFee, SQLiteApiError
from finance_cli.service import (
    FundInfoChange,
    FundInfoSyncFailure,
    FundInfoSyncResult,
    FundInfoSyncSuccess,
    MetricQueryResult,
    MetricRangeQueryResult,
)
from finance_cli.sources import DataSourceError


runner = CliRunner()


def _fund_info_payload():
    return {
        "code": "017763",
        "name": "银河领先债券C",
        "fund_type": "债券型",
        "established_date": "2023-01-01",
        "asset_size": "10.25亿元",
        "operation_fee": {
            "total": 0.004,
            "management_fee": 0.003,
            "custodian_fee": 0.001,
            "sales_service_fee": 0.0,
        },
        "purchase_status": "开放申购",
        "purchase_limit_amount": 1000.0,
        "redemption_status": "开放赎回",
        "morningstar_rating": "5",
        "purchase_fee": [
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            }
        ],
        "redemption_fee": [
            {
                "min_holding_days": 0,
                "max_holding_days": 7,
                "original_rate": 0.015,
                "discounted_rate": 0.015,
            }
        ],
        "source": "manual",
        "updated_at": "2026-06-07T12:00:00+00:00",
    }


def test_cli_help_shows_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pe" in result.output
    assert "dividend-yield" in result.output
    assert "pb" in result.output
    assert "fund-nav" in result.output
    assert "fund-info" in result.output
    assert "fund-info-update" in result.output
    assert "cn10y-yield" in result.output
    assert "gold" in result.output
    assert "erp" in result.output
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


def test_pe_command_accepts_sp500(monkeypatch, tmp_path):
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
            "2026-06-05",
            "2016-06-06",
            28.2749,
            65.0,
            522,
            "danjuan",
            years,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)

    result = runner.invoke(app, ["pe", "--code", "sp500", "--json"])

    assert result.exit_code == 0
    assert seen["code"] == "SP500"


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


def test_fund_nav_command_outputs_money_fund_metrics_when_nav_trend_missing(monkeypatch):
    calls = []

    def query_value(self, asset_type, code, metric, requested_date, fetch_missing):
        calls.append(metric)
        if metric == "unit_nav":
            raise DataSourceError("Failed to fetch fund NAV rows for 001821: Data_netWorthTrend is not defined")
        if metric == "million_copies_income":
            return MetricQueryResult(
                asset_type,
                code,
                metric,
                requested_date,
                "2026-06-07",
                None,
                0.3571,
                None,
                None,
                "akshare",
                None,
            )
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-06-07",
            None,
            1.342,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(
        app,
        ["fund-nav", "--code", "001821", "--date", "2026-06-08", "--json"],
    )

    assert result.exit_code == 0
    assert calls == ["unit_nav", "million_copies_income", "seven_day_annualized_yield"]
    payload = json.loads(result.output)
    assert payload == {
        "asset_type": "fund",
        "code": "001821",
        "fund_type": "货币基金",
        "requested_date": "2026-06-08",
        "actual_date": "2026-06-07",
        "metrics": {
            "million_copies_income": 0.3571,
            "seven_day_annualized_yield": 1.342,
        },
        "source": "akshare",
    }


def test_fund_nav_command_outputs_money_fund_metrics_text(monkeypatch):
    def query_value(self, asset_type, code, metric, requested_date, fetch_missing):
        if metric == "unit_nav":
            raise DataSourceError("Failed to fetch fund NAV rows for 001821: Data_netWorthTrend is not defined")
        value = 0.3571 if metric == "million_copies_income" else 1.342
        return MetricQueryResult(
            asset_type,
            code,
            metric,
            requested_date,
            "2026-06-07",
            None,
            value,
            None,
            None,
            "akshare",
            None,
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_value", query_value)

    result = runner.invoke(app, ["fund-nav", "--code", "001821", "--date", "2026-06-08"])

    assert result.exit_code == 0
    assert "基金类型: 货币基金" in result.output
    assert "每万份收益: 0.3571" in result.output
    assert "7日年化收益率: 1.342" in result.output


def test_fund_nav_command_outputs_money_fund_range_json(monkeypatch):
    calls = []

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        calls.append(metric)
        if metric == "unit_nav":
            raise DataSourceError("Failed to fetch fund NAV rows for 001821: Data_netWorthTrend is not defined")
        values = [("2026-06-06", 0.3571), ("2026-06-07", 0.3572)]
        if metric == "seven_day_annualized_yield":
            values = [("2026-06-06", 1.343), ("2026-06-07", 1.342)]
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-06-06",
            "2026-06-07",
            [(row_date, value, "akshare") for row_date, value in values],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["fund-nav", "--code", "001821", "--from", "2026-06-06", "--to", "2026-06-08", "--json"],
    )

    assert result.exit_code == 0
    assert calls == ["unit_nav", "million_copies_income", "seven_day_annualized_yield"]
    payload = json.loads(result.output)
    assert payload == {
        "asset_type": "fund",
        "code": "001821",
        "fund_type": "货币基金",
        "requested_from": "2026-06-06",
        "requested_to": "2026-06-08",
        "actual_start_date": "2026-06-06",
        "actual_end_date": "2026-06-07",
        "data": [
            {
                "date": "2026-06-06",
                "metrics": {
                    "million_copies_income": 0.3571,
                    "seven_day_annualized_yield": 1.343,
                },
                "source": "akshare",
            },
            {
                "date": "2026-06-07",
                "metrics": {
                    "million_copies_income": 0.3572,
                    "seven_day_annualized_yield": 1.342,
                },
                "source": "akshare",
            },
        ],
    }


def test_fund_info_command_outputs_cached_json(monkeypatch):
    seen = {}

    def query_fund_info(self, code, fetch_missing, refresh=False):
        seen["code"] = code
        seen["refresh"] = refresh
        return FundInfo(**_fund_info_payload())

    monkeypatch.setattr("finance_cli.service.MetricsService.query_fund_info", query_fund_info)

    result = runner.invoke(app, ["fund-info", "--code", "017763", "--json"])

    assert result.exit_code == 0
    assert seen == {"code": "017763", "refresh": False}
    payload = json.loads(result.output)
    assert payload["code"] == "017763"
    assert payload["name"] == "银河领先债券C"
    assert "management_fee" not in payload
    assert payload["operation_fee"] == {
        "total": 0.004,
        "management_fee": 0.003,
        "custodian_fee": 0.001,
        "sales_service_fee": 0.0,
    }
    assert payload["purchase_fee"][0]["discounted_rate"] == 0.0015


def test_fund_info_command_passes_refresh(monkeypatch):
    seen = {}

    def query_fund_info(self, code, fetch_missing, refresh=False):
        seen["refresh"] = refresh
        return FundInfo(**_fund_info_payload())

    monkeypatch.setattr("finance_cli.service.MetricsService.query_fund_info", query_fund_info)

    result = runner.invoke(app, ["fund-info", "--code", "017763", "--refresh"])

    assert result.exit_code == 0
    assert seen["refresh"] is True
    assert "基金名称: 银河领先债券C" in result.output


def test_fund_info_update_accepts_inline_json(monkeypatch):
    seen = {}

    def update_fund_info(self, fund_info):
        seen["fund_info"] = fund_info
        return fund_info

    monkeypatch.setattr("finance_cli.service.MetricsService.update_fund_info", update_fund_info)

    result = runner.invoke(
        app,
        [
            "fund-info-update",
            "--code",
            "017763",
            "--data",
            json.dumps(_fund_info_payload(), ensure_ascii=False),
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert seen["fund_info"].code == "017763"
    assert seen["fund_info"].operation_fee == OperationFee(
        management_fee=0.003,
        custodian_fee=0.001,
        sales_service_fee=0.0,
    )
    assert seen["fund_info"].purchase_limit_amount == 1000.0
    assert seen["fund_info"].source == "manual"
    payload = json.loads(result.output)
    assert payload["name"] == "银河领先债券C"


def test_fund_info_update_accepts_json_file(monkeypatch, tmp_path):
    seen = {}

    def update_fund_info(self, fund_info):
        seen["fund_info"] = fund_info
        return fund_info

    data_file = tmp_path / "fund-info.json"
    data_file.write_text(json.dumps(_fund_info_payload(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("finance_cli.service.MetricsService.update_fund_info", update_fund_info)

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data-file", str(data_file), "--json"],
    )

    assert result.exit_code == 0
    assert seen["fund_info"].code == "017763"


def test_fund_info_update_accepts_null_purchase_limit_amount(monkeypatch):
    seen = {}
    payload = _fund_info_payload()
    payload["purchase_limit_amount"] = None

    def update_fund_info(self, fund_info):
        seen["fund_info"] = fund_info
        return fund_info

    monkeypatch.setattr("finance_cli.service.MetricsService.update_fund_info", update_fund_info)

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code == 0
    assert seen["fund_info"].purchase_limit_amount is None


def test_fund_info_update_rejects_data_and_data_file_conflict(tmp_path):
    data_file = tmp_path / "fund-info.json"
    data_file.write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "fund-info-update",
            "--code",
            "017763",
            "--data",
            "{}",
            "--data-file",
            str(data_file),
            "--json",
        ],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "invalid_parameter"
    assert "--data and --data-file cannot be used together" in payload["error"]["message"]


def test_fund_info_update_rejects_unknown_field():
    payload = _fund_info_payload()
    payload["unexpected"] = "bad"

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "Unknown fund info fields" in error["message"]


def test_fund_info_update_rejects_code_mismatch():
    payload = _fund_info_payload()
    payload["code"] = "000001"

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "JSON code must match --code" in error["message"]


def test_fund_info_update_rejects_missing_data_inputs():
    result = runner.invoke(app, ["fund-info-update", "--code", "017763", "--json"])

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "one of --data or --data-file is required" in error["message"]


def test_fund_info_update_rejects_invalid_json():
    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", "{bad", "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "invalid JSON" in error["message"]


def test_fund_info_update_rejects_invalid_fee_tier_shape():
    payload = _fund_info_payload()
    payload["purchase_fee"] = [
        {
            "min_amount": "zero",
            "max_amount": 1000000,
            "original_rate": 0.015,
            "discounted_rate": 0.0015,
        }
    ]

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "purchase_fee min_amount must be a number" in error["message"]


def test_fund_info_update_rejects_invalid_purchase_limit_amount():
    payload = _fund_info_payload()
    payload["purchase_limit_amount"] = "1000"

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "purchase_limit_amount must be a number" in error["message"]


def test_fund_info_update_rejects_top_level_management_fee():
    payload = _fund_info_payload()
    payload["management_fee"] = 0.003

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "Unknown fund info fields: management_fee" in error["message"]


def test_fund_info_update_rejects_invalid_operation_fee_rate():
    payload = _fund_info_payload()
    payload["operation_fee"]["management_fee"] = "0.30%/年"

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "operation_fee management_fee must be a number or null" in error["message"]


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


def test_sync_pe_accepts_sp500(monkeypatch, tmp_path):
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

    result = runner.invoke(app, ["sync", "pe", "--code", "sp500"])

    assert result.exit_code == 0
    assert seen["asset_type"] == "index"
    assert seen["sync_code"] == "SP500"
    assert seen["metric"] == "rolling_pe"
    assert seen["code"] == "SP500"
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


def test_sync_fund_info_outputs_summary_and_highlighted_changes(monkeypatch):
    highlighted = []

    def sync_fund_info(self, fetcher, max_workers=5):
        return FundInfoSyncResult(
            total=2,
            successes=[
                FundInfoSyncSuccess(
                    code="017763",
                    name="银河领先债券C",
                    changes=[
                        FundInfoChange(
                            field="purchase_status",
                            label="申购状态",
                            old="开放申购",
                            new="暂停申购",
                        )
                    ],
                ),
                FundInfoSyncSuccess(code="008887", name="华夏国证半导体芯片ETF联接A", changes=[]),
            ],
            failures=[],
        )

    def secho(message, fg=None, bold=False):
        highlighted.append((message, fg, bold))

    monkeypatch.setattr("finance_cli.service.MetricsService.sync_fund_info", sync_fund_info)
    monkeypatch.setattr("finance_cli.cli.typer.secho", secho)

    result = runner.invoke(app, ["sync", "fund-info"])

    assert result.exit_code == 0
    assert "同步基金基本信息：共 2 只，成功 2 只，失败 0 只" in result.output
    assert highlighted == [
        (
            "重要变更 017763 银河领先债券C: 申购状态 开放申购 -> 暂停申购",
            "yellow",
            True,
        )
    ]


def test_sync_fund_info_outputs_failures_without_failing_when_some_succeed(monkeypatch):
    def sync_fund_info(self, fetcher, max_workers=5):
        return FundInfoSyncResult(
            total=2,
            successes=[FundInfoSyncSuccess(code="008887", name="华夏国证半导体芯片ETF联接A", changes=[])],
            failures=[FundInfoSyncFailure(code="017763", error="source failed")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.sync_fund_info", sync_fund_info)

    result = runner.invoke(app, ["sync", "fund-info"])

    assert result.exit_code == 0
    assert "同步基金基本信息：共 2 只，成功 1 只，失败 1 只" in result.output
    assert "失败 017763: source failed" in result.output


def test_sync_fund_info_fails_when_all_refreshes_fail(monkeypatch):
    def sync_fund_info(self, fetcher, max_workers=5):
        return FundInfoSyncResult(
            total=1,
            successes=[],
            failures=[FundInfoSyncFailure(code="017763", error="source failed")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.sync_fund_info", sync_fund_info)

    result = runner.invoke(app, ["sync", "fund-info"])

    assert result.exit_code != 0
    assert "All fund info refreshes failed" in result.output


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


def test_dividend_yield_spread_command_fetches_combined_dividend_yield_rows(monkeypatch):
    fetched_codes = []
    upserted = []

    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        fetch_missing()
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2016-01-08", 2.88, 35.0, 2500,
            "akshare", years,
        )

    def fetch_dividend_rows(code):
        fetched_codes.append(code)
        return [DailyMetric("index", code, "dividend_yield", "2016-01-08", 3.15, "funddb")]

    def fetch_cn10y_rows():
        return [DailyMetric("bond", "CN10Y", "yield", "2016-01-08", 2.0, "akshare")]

    def upsert_metrics(self, rows):
        upserted.extend(rows)

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        if metric == "dividend_yield":
            return [DailyMetric("index", code, metric, "2016-01-08", 3.15, "funddb")]
        if metric == "yield":
            return [DailyMetric("bond", "CN10Y", metric, "2026-05-29", 1.62, "akshare")]
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.cli.fetch_index_dividend_yield_rows", fetch_dividend_rows)
    monkeypatch.setattr("finance_cli.cli.fetch_cn10y_yield_rows", fetch_cn10y_rows)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.upsert_metrics", upsert_metrics)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["dividend-yield-spread", "--code", "SH000922", "--json"])

    assert result.exit_code == 0
    assert fetched_codes == ["000922"]
    assert [(row.asset_type, row.code, row.metric, row.date, row.source) for row in upserted] == [
        ("index", "000922", "dividend_yield", "2016-01-08", "funddb"),
        ("bond", "CN10Y", "yield", "2016-01-08", "akshare"),
    ]


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


def test_erp_command_outputs_json(monkeypatch):
    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        assert ensure_lookback_coverage is True
        assert minimum_lookback_years == 3
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2020-01-02", 2.5, 35.0, 1500,
            "akshare", years,
        )

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        if metric == "rolling_pe":
            return [DailyMetric("index", code, metric, "2026-05-29", 20.0, "akshare")]
        if metric == "yield":
            return [DailyMetric("bond", "CN10Y", metric, "2026-05-29", 2.5, "akshare")]
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["erp", "--code", "000300", "--years", "5", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["asset_type"] == "spread"
    assert payload["code"] == "000300"
    assert payload["metric"] == "erp"
    assert payload["value"] == 2.5
    assert payload["percentile"] == 35.0
    assert payload["lookback_years"] == 5
    assert payload["pe_ttm"] == 20.0
    assert payload["earnings_yield"] == 5.0
    assert payload["cn10y_yield"] == 2.5


def test_erp_command_outputs_text(monkeypatch):
    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2020-01-02", 2.5, 35.0, 1500,
            "akshare", years,
        )

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        if metric == "rolling_pe":
            return [DailyMetric("index", code, metric, "2026-05-29", 20.0, "akshare")]
        if metric == "yield":
            return [DailyMetric("bond", "CN10Y", metric, "2026-05-29", 2.5, "akshare")]
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["erp", "--code", "000300", "--years", "5"])

    assert result.exit_code == 0
    assert "利差: 000300" in result.output
    assert "股债利差（ERP）: 2.5" in result.output
    assert "历史百分位: 35.0%" in result.output
    assert "回看年数: 5" in result.output
    assert "PE_TTM: 20.0" in result.output
    assert "盈利收益率: 5.0" in result.output
    assert "10年期国债收益率: 2.5" in result.output


def test_erp_command_normalizes_exchange_prefixed_code(monkeypatch):
    seen_code = {}

    def query(
        self, asset_type, code, metric, requested_date, years, fetch_missing,
        ensure_lookback_coverage=False, minimum_lookback_years=None,
    ):
        seen_code["code"] = code
        return MetricQueryResult(
            asset_type, code, metric, requested_date,
            "2026-05-29", "2020-01-02", 2.5, 35.0, 1500,
            "akshare", years,
        )

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        return []

    monkeypatch.setattr("finance_cli.service.MetricsService.query", query)
    monkeypatch.setattr("finance_cli.db.MetricsRepository.metrics_between", metrics_between)

    result = runner.invoke(app, ["erp", "--code", "SH000300", "--json"])

    assert result.exit_code == 0
    assert seen_code["code"] == "000300"


def test_erp_range_command_outputs_json(monkeypatch):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type, code, metric, requested_from, requested_to,
            "2026-01-02", "2026-04-30",
            [("2026-04-30", 2.5, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["erp", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "spread", "code": "000300", "metric": "erp"}


def test_sync_erp_outputs_inserted_count(monkeypatch):
    def sync(self, fetch_rows):
        return 2000

    monkeypatch.setattr("finance_cli.service.MetricsService.sync", sync)

    result = runner.invoke(app, ["sync", "erp", "--code", "000300"])

    assert result.exit_code == 0
    assert "同步 2000 条记录" in result.output
