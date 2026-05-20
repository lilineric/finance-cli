import pandas as pd
import pytest

from finance_cli.sources import (
    DataSourceError,
    fetch_gold_rows,
    fetch_index_pe_rows,
    normalize_gold_rows,
    normalize_index_pe_rows,
)


def test_normalize_index_pe_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "滚动市盈率": [12.3, 12.8],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "pe_ttm", "2026-04-17", 12.3, "akshare"),
        ("index", "000300", "pe_ttm", "2026-04-20", 12.8, "akshare"),
    ]


def test_normalize_index_pe_rows_prefers_documented_calculation_share_pe():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17"],
            "市盈率1": [13.1],
            "市盈率2": [12.3],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "pe_ttm", "2026-04-17", 12.3, "akshare"),
    ]


def test_normalize_gold_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "收盘价": [530.5, 535.2],
        }
    )

    rows = normalize_gold_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("gold", "AU9999", "close", "2026-04-17", 530.5, "akshare"),
        ("gold", "AU9999", "close", "2026-04-20", 535.2, "akshare"),
    ]


@pytest.mark.parametrize("date_value", [None, pd.NA, "", float("nan")])
def test_normalize_gold_rows_rejects_missing_dates(date_value):
    frame = pd.DataFrame({"日期": [date_value], "收盘价": [530.5]})

    with pytest.raises(DataSourceError):
        normalize_gold_rows(frame)


@pytest.mark.parametrize("numeric_value", [None, pd.NA, "", float("nan")])
def test_normalize_gold_rows_rejects_missing_numeric_values(numeric_value):
    frame = pd.DataFrame({"日期": ["2026-04-17"], "收盘价": [numeric_value]})

    with pytest.raises(DataSourceError):
        normalize_gold_rows(frame)


def test_fetch_index_pe_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "市盈率2": [12.3]})

    rows = fetch_index_pe_rows("000300", fetcher=fetcher)

    assert calls == [{"symbol": "000300"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "pe_ttm", "2026-04-17", 12.3, "akshare"),
    ]


def test_fetch_gold_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "收盘价": [530.5]})

    rows = fetch_gold_rows(fetcher=fetcher)

    assert calls == [{"symbol": "Au99.99"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("gold", "AU9999", "close", "2026-04-17", 530.5, "akshare"),
    ]
