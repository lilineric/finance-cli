from datetime import date

import pandas as pd
import pytest

from finance_cli.sources import (
    DataSourceError,
    fetch_cn10y_yield_rows,
    fetch_gold_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_pe_rows,
    fetch_sw_index_pb_rows,
    normalize_csindex_code,
    normalize_cn10y_yield_rows,
    normalize_gold_rows,
    normalize_index_dividend_yield_rows,
    normalize_index_pe_rows,
    normalize_sw_index_pb_rows,
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


def test_fetch_index_pe_rows_normalizes_exchange_prefixed_code():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "市盈率2": [12.3]})

    rows = fetch_index_pe_rows("SH000300", fetcher=fetcher)

    assert calls == [{"symbol": "000300"}]
    assert rows[0].code == "000300"


def test_normalize_csindex_code_rejects_invalid_code():
    with pytest.raises(DataSourceError, match="Invalid index code"):
        normalize_csindex_code("SH300")


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


def test_normalize_index_dividend_yield_rows_prefers_documented_calculation_share_yield():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17"],
            "股息率1": [2.8],
            "股息率2": [3.1],
        }
    )

    rows = normalize_index_dividend_yield_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "dividend_yield", "2026-04-17", 3.1, "akshare"),
    ]


def test_fetch_index_dividend_yield_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "股息率2": [3.1]})

    rows = fetch_index_dividend_yield_rows("000300", fetcher=fetcher)

    assert calls == [{"symbol": "000300"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "dividend_yield", "2026-04-17", 3.1, "akshare"),
    ]


def test_normalize_sw_index_pb_rows_filters_code_and_reads_pb():
    frame = pd.DataFrame(
        {
            "发布日期": ["2026-04-17", "2026-04-17"],
            "指数代码": ["801010", "801020"],
            "市净率": [1.8, 2.3],
        }
    )

    rows = normalize_sw_index_pb_rows("801010", "一级行业", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("sw_index:一级行业", "801010", "pb", "2026-04-17", 1.8, "akshare"),
    ]


def test_normalize_sw_index_pb_rows_rejects_missing_code():
    frame = pd.DataFrame({"日期": ["2026-04-17"], "指数代码": ["801020"], "市净率": [2.3]})

    with pytest.raises(DataSourceError, match="No PB data"):
        normalize_sw_index_pb_rows("801010", "一级行业", frame)


def test_fetch_sw_index_pb_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"发布日期": ["2026-04-17"], "指数代码": ["801010"], "市净率": [1.8]})

    rows = fetch_sw_index_pb_rows("801010", "一级行业", fetcher=fetcher)

    assert calls == [{"symbol": "一级行业", "start_date": "19900101", "end_date": date.today().strftime("%Y%m%d")}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("sw_index:一级行业", "801010", "pb", "2026-04-17", 1.8, "akshare"),
    ]


def test_normalize_cn10y_yield_rows_reads_china_10y_column():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "中国国债收益率10年": [1.7, 1.8],
        }
    )

    rows = normalize_cn10y_yield_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "CN10Y", "yield", "2026-04-17", 1.7, "akshare"),
        ("bond", "CN10Y", "yield", "2026-04-20", 1.8, "akshare"),
    ]


def test_fetch_cn10y_yield_rows_uses_injected_fetcher_without_network():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "中国国债收益率10年": [1.7]})

    rows = fetch_cn10y_yield_rows(fetcher=fetcher)

    assert calls == [{"start_date": "19901219"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "CN10Y", "yield", "2026-04-17", 1.7, "akshare"),
    ]
