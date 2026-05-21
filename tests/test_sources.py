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
        ("index", "000300", "rolling_pe", "2026-04-17", 12.3, "akshare"),
        ("index", "000300", "rolling_pe", "2026-04-20", 12.8, "akshare"),
    ]


def test_normalize_index_pe_rows_prefers_rolling_pe():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17"],
            "市盈率2": [12.3],
            "滚动市盈率": [14.2],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "rolling_pe", "2026-04-17", 14.2, "akshare"),
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


def test_fetch_index_pe_rows_uses_injected_fetcher_with_10_year_window(monkeypatch):
    calls = []

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 21)

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "滚动市盈率": [12.3]})

    monkeypatch.setattr("finance_cli.sources.date", FixedDate)
    rows = fetch_index_pe_rows("000300", fetcher=fetcher)

    assert calls == [{"symbol": "000300", "start_date": "20160521", "end_date": "20260521"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "rolling_pe", "2026-04-17", 12.3, "akshare"),
    ]


def test_fetch_index_pe_rows_normalizes_exchange_prefixed_code(monkeypatch):
    calls = []

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 21)

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"日期": ["2026-04-17"], "滚动市盈率": [12.3]})

    monkeypatch.setattr("finance_cli.sources.date", FixedDate)
    rows = fetch_index_pe_rows("SH000300", fetcher=fetcher)

    assert calls == [{"symbol": "000300", "start_date": "20160521", "end_date": "20260521"}]
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


def test_fetch_index_dividend_yield_rows_filters_to_latest_date_on_or_before_query_date():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            {
                "日期": ["2026-04-17", "2026-04-20", "2026-04-21"],
                "股息率2": [3.1, 3.2, 3.3],
            }
        )

    rows = fetch_index_dividend_yield_rows("000300", query_date="2026-04-20", fetcher=fetcher)

    assert calls == [{"symbol": "000300"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("index", "000300", "dividend_yield", "2026-04-20", 3.2, "akshare"),
    ]


def test_fetch_index_dividend_yield_rows_without_query_date_returns_all_rows():
    def fetcher(**kwargs):
        return pd.DataFrame({"日期": ["2026-04-17", "2026-04-20"], "股息率2": [3.1, 3.2]})

    rows = fetch_index_dividend_yield_rows("000300", fetcher=fetcher)

    assert [row.date for row in rows] == ["2026-04-17", "2026-04-20"]


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


def test_fetch_sw_index_pb_rows_uses_injected_fetcher_with_query_date():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"发布日期": ["2026-04-17"], "指数代码": ["801010"], "市净率": [1.8]})

    rows = fetch_sw_index_pb_rows("801010", "一级行业", query_date="2026-04-17", fetcher=fetcher)

    assert calls == [{"symbol": "一级行业", "start_date": "20260407", "end_date": "20260417"}]
    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("sw_index:一级行业", "801010", "pb", "2026-04-17", 1.8, "akshare"),
    ]


def test_fetch_sw_index_pb_rows_wraps_akshare_empty_result_key_error():
    def fetcher(**kwargs):
        raise KeyError("发布日期")

    with pytest.raises(DataSourceError, match="No SW index PB data available on or before 2026-05-22"):
        fetch_sw_index_pb_rows("801010", "一级行业", query_date="2026-05-22", fetcher=fetcher)


def test_fetch_sw_index_pb_rows_reports_code_missing_from_category():
    def fetcher(**kwargs):
        return pd.DataFrame({"发布日期": ["2026-05-20"], "指数代码": ["801010"], "市净率": [2.38]})

    with pytest.raises(DataSourceError, match="No PB data found for SW index 000300 in 一级行业"):
        fetch_sw_index_pb_rows("000300", "一级行业", query_date="2026-05-22", fetcher=fetcher)


def test_fetch_sw_index_pb_rows_without_query_date_keeps_history_sync_window():
    calls = []

    def fetcher(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame({"发布日期": ["2026-04-17"], "指数代码": ["801010"], "市净率": [1.8]})

    fetch_sw_index_pb_rows("801010", "一级行业", fetcher=fetcher)

    assert calls == [{"symbol": "一级行业", "start_date": "19900101", "end_date": date.today().strftime("%Y%m%d")}]


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


def test_normalize_cn10y_yield_rows_skips_missing_yields():
    frame = pd.DataFrame(
        {
            "日期": ["1990-12-19", "2026-05-21"],
            "中国国债收益率10年": [float("nan"), 1.7448],
        }
    )

    rows = normalize_cn10y_yield_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value, row.source) for row in rows] == [
        ("bond", "CN10Y", "yield", "2026-05-21", 1.7448, "akshare"),
    ]


def test_normalize_cn10y_yield_rows_rejects_all_missing_yields():
    frame = pd.DataFrame(
        {
            "日期": ["1990-12-19"],
            "中国国债收益率10年": [float("nan")],
        }
    )

    with pytest.raises(DataSourceError, match="No valid CN10Y yield data"):
        normalize_cn10y_yield_rows(frame)


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
