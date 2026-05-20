import json

from finance_cli.output import format_json, format_text
from finance_cli.service import MetricQueryResult


def test_format_json_uses_stable_keys():
    result = MetricQueryResult("index", "000300", "pe_ttm", "2026-04-20", "2026-04-17", 12.34, 42.8, 2000, "akshare")

    payload = json.loads(format_json(result))

    assert payload["asset_type"] == "index"
    assert payload["code"] == "000300"
    assert payload["metric"] == "pe_ttm"
    assert payload["requested_date"] == "2026-04-20"
    assert payload["actual_date"] == "2026-04-17"
    assert payload["value"] == 12.34
    assert payload["percentile"] == 42.8
    assert payload["sample_count"] == 2000
    assert payload["source"] == "akshare"


def test_format_text_includes_key_fields():
    result = MetricQueryResult("gold", "AU9999", "close", "2026-04-20", "2026-04-17", 535.2, 80.0, 2400, "akshare")

    text = format_text(result)

    assert "AU9999" in text
    assert "2026-04-20" in text
    assert "2026-04-17" in text
    assert "535.2" in text
    assert "80.0%" in text
    assert "2400" in text
