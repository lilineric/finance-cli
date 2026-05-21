import json

from finance_cli.output import format_json, format_text
from finance_cli.service import MetricQueryResult


def test_format_json_uses_stable_keys():
    result = MetricQueryResult("index", "000300", "rolling_pe", "2026-04-20", "2026-04-17", "2020-01-02", 12.34, 42.8, 2000, "akshare", 10)

    payload = json.loads(format_json(result))

    assert set(payload) == {
        "asset_type",
        "code",
        "metric",
        "requested_date",
        "actual_date",
        "sample_start_date",
        "value",
        "percentile",
        "sample_count",
        "source",
        "lookback_years",
    }
    assert payload["asset_type"] == "index"
    assert payload["code"] == "000300"
    assert payload["metric"] == "rolling_pe"
    assert payload["requested_date"] == "2026-04-20"
    assert payload["actual_date"] == "2026-04-17"
    assert payload["sample_start_date"] == "2020-01-02"
    assert payload["value"] == 12.34
    assert payload["percentile"] == 42.8
    assert payload["sample_count"] == 2000
    assert payload["source"] == "akshare"
    assert payload["lookback_years"] == 10


def test_format_text_includes_index_pe_labels_and_key_fields():
    result = MetricQueryResult("index", "000300", "rolling_pe", "2026-04-20", "2026-04-17", "2020-01-02", 12.34, 42.8, 2000, "akshare", 10)

    text = format_text(result)

    assert "指数: 000300" in text
    assert "请求日期: 2026-04-20" in text
    assert "实际数据日期: 2026-04-17" in text
    assert "滚动市盈率: 12.34" in text
    assert "历史百分位: 42.8%" in text
    assert "样本数: 2000" in text
    assert "样本起始日期: 2020-01-02" in text
    assert "回看年数: 10" in text


def test_format_text_includes_gold_close_labels_and_key_fields():
    result = MetricQueryResult("gold", "AU9999", "close", "2026-04-20", "2026-04-17", "2021-03-01", 535.2, 80.0, 2400, "akshare", 5)

    text = format_text(result)

    assert "黄金: AU9999" in text
    assert "请求日期: 2026-04-20" in text
    assert "实际数据日期: 2026-04-17" in text
    assert "收盘价: 535.2" in text
    assert "历史百分位: 80.0%" in text
    assert "样本数: 2400" in text
    assert "样本起始日期: 2021-03-01" in text
    assert "回看年数: 5" in text


def test_format_output_omits_percentile_when_unavailable():
    result = MetricQueryResult(
        "index",
        "000300",
        "dividend_yield",
        "2026-05-22",
        "2026-05-21",
        None,
        2.32,
        None,
        None,
        "akshare",
        None,
    )

    payload = json.loads(format_json(result))
    text = format_text(result)

    assert "percentile" not in payload
    assert "lookback_years" not in payload
    assert "sample_count" not in payload
    assert "sample_start_date" not in payload
    assert "股息率: 2.32" in text
    assert "历史百分位" not in text
    assert "回看年数" not in text
    assert "样本数" not in text
    assert "样本起始日期" not in text


def test_format_text_includes_new_metric_labels():
    dividend = MetricQueryResult("index", "000300", "dividend_yield", "2026-04-20", "2026-04-17", "2020-01-02", 3.1, 70.0, 2000, "akshare", 10)
    pb = MetricQueryResult("sw_index:一级行业", "801010", "pb", "2026-04-20", "2026-04-17", "2020-01-02", 1.8, 35.0, 2000, "akshare", 10)
    cn10y = MetricQueryResult("bond", "CN10Y", "yield", "2026-04-20", "2026-04-17", "2020-01-02", 1.7, 20.0, 2000, "akshare", 10)

    assert "股息率: 3.1" in format_text(dividend)
    assert "PB: 1.8" in format_text(pb)
    assert "收益率: 1.7" in format_text(cn10y)
