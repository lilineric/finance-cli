import json

from finance_cli.output import format_json, format_text
from finance_cli.service import MetricQueryResult


def test_format_json_uses_stable_keys():
    result = MetricQueryResult("index", "000300", "pe_ttm", "2026-04-20", "2026-04-17", 12.34, 42.8, 2000, "akshare", 10)

    payload = json.loads(format_json(result))

    assert set(payload) == {
        "asset_type",
        "code",
        "metric",
        "requested_date",
        "actual_date",
        "value",
        "percentile",
        "sample_count",
        "source",
        "lookback_years",
    }
    assert payload["asset_type"] == "index"
    assert payload["code"] == "000300"
    assert payload["metric"] == "pe_ttm"
    assert payload["requested_date"] == "2026-04-20"
    assert payload["actual_date"] == "2026-04-17"
    assert payload["value"] == 12.34
    assert payload["percentile"] == 42.8
    assert payload["sample_count"] == 2000
    assert payload["source"] == "akshare"
    assert payload["lookback_years"] == 10


def test_format_text_includes_index_pe_labels_and_key_fields():
    result = MetricQueryResult("index", "000300", "pe_ttm", "2026-04-20", "2026-04-17", 12.34, 42.8, 2000, "akshare", 10)

    text = format_text(result)

    assert "指数: 000300" in text
    assert "请求日期: 2026-04-20" in text
    assert "实际数据日期: 2026-04-17" in text
    assert "PE-TTM: 12.34" in text
    assert "历史百分位: 42.8%" in text
    assert "样本数: 2000" in text
    assert "回看年数: 10" in text


def test_format_text_includes_gold_close_labels_and_key_fields():
    result = MetricQueryResult("gold", "AU9999", "close", "2026-04-20", "2026-04-17", 535.2, 80.0, 2400, "akshare", 5)

    text = format_text(result)

    assert "黄金: AU9999" in text
    assert "请求日期: 2026-04-20" in text
    assert "实际数据日期: 2026-04-17" in text
    assert "收盘价: 535.2" in text
    assert "历史百分位: 80.0%" in text
    assert "样本数: 2400" in text
    assert "回看年数: 5" in text
