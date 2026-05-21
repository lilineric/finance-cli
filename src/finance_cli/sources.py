from datetime import date, datetime, timedelta
import re
from typing import Callable

import pandas as pd

from finance_cli.analytics import parse_query_date, start_date_for_years
from finance_cli.db import DailyMetric


INDEX_PE_DATE_COLUMNS = ("日期", "date", "trade_date")
INDEX_PE_VALUE_COLUMNS = ("滚动市盈率", "市盈率TTM")
INDEX_DIVIDEND_YIELD_VALUE_COLUMNS = ("股息率2", "股息率1", "股息率", "dividend_yield")
SW_INDEX_DATE_COLUMNS = ("发布日期", "日期", "date", "trade_date")
SW_INDEX_CODE_COLUMNS = ("指数代码", "code", "index_code")
SW_INDEX_PB_VALUE_COLUMNS = ("市净率", "pb", "PB")
GOLD_DATE_COLUMNS = ("日期", "date", "trade_date")
GOLD_CLOSE_COLUMNS = ("收盘价", "close", "收盘")
CN10Y_YIELD_DATE_COLUMNS = ("日期", "date", "trade_date")
CN10Y_YIELD_VALUE_COLUMNS = ("中国国债收益率10年", "中国10年期国债收益率", "cn10y", "yield")


class DataSourceError(RuntimeError):
    pass


def fetch_index_pe_rows(code: str, fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    normalized_code = normalize_csindex_code(code)
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.stock_zh_index_hist_csindex

    try:
        today = date.today()
        frame = fetcher(
            symbol=normalized_code,
            start_date=start_date_for_years(today, 10).strftime("%Y%m%d"),
            end_date=today.strftime("%Y%m%d"),
        )
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch index PE rows for {code}: {exc}") from exc

    return normalize_index_pe_rows(normalized_code, frame)


def fetch_index_dividend_yield_rows(
    code: str,
    fetcher: Callable[..., pd.DataFrame] | None = None,
    query_date: str | None = None,
) -> list[DailyMetric]:
    normalized_code = normalize_csindex_code(code)
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.stock_zh_index_value_csindex

    try:
        frame = fetcher(symbol=normalized_code)
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch index dividend yield rows for {code}: {exc}") from exc

    rows = normalize_index_dividend_yield_rows(normalized_code, frame)
    if query_date is None:
        return rows

    requested_date = parse_query_date(query_date).isoformat()
    eligible_rows = [row for row in rows if row.date <= requested_date]
    if not eligible_rows:
        raise DataSourceError(
            f"No dividend yield data found for index {normalized_code} on or before {requested_date}"
        )
    return [max(eligible_rows, key=lambda row: row.date)]


def normalize_csindex_code(code: str) -> str:
    normalized = code.strip().upper()
    if normalized.startswith(("SH", "SZ")):
        normalized = normalized[2:]
    if not re.fullmatch(r"\d{6}", normalized):
        raise DataSourceError(f"Invalid index code: {code}")
    return normalized


def fetch_sw_index_pb_rows(
    code: str,
    category: str,
    fetcher: Callable[..., pd.DataFrame] | None = None,
    query_date: str | None = None,
) -> list[DailyMetric]:
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.index_analysis_daily_sw

    try:
        if query_date is None:
            start_date = "19900101"
            end_date = date.today().strftime("%Y%m%d")
        else:
            parsed_requested_date = parse_query_date(query_date)
            start_date = (parsed_requested_date - timedelta(days=10)).strftime("%Y%m%d")
            end_date = parsed_requested_date.strftime("%Y%m%d")
        frame = fetcher(symbol=category, start_date=start_date, end_date=end_date)
    except KeyError as exc:
        if query_date is not None and str(exc).strip("'\"") == "发布日期":
            requested_date = parse_query_date(query_date).isoformat()
            raise DataSourceError(
                f"No SW index PB data available on or before {requested_date}"
            ) from exc
        raise DataSourceError(f"Failed to fetch SW index PB rows for {code}: {exc}") from exc
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch SW index PB rows for {code}: {exc}") from exc

    return normalize_sw_index_pb_rows(code, category, frame)


def fetch_gold_rows(fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.spot_hist_sge

    try:
        frame = fetcher(symbol="Au99.99")
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch gold rows: {exc}") from exc

    return normalize_gold_rows(frame)


def fetch_cn10y_yield_rows(fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.bond_zh_us_rate

    try:
        frame = fetcher(start_date="19901219")
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch CN10Y yield rows: {exc}") from exc

    return normalize_cn10y_yield_rows(frame)


def normalize_index_pe_rows(code: str, frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, INDEX_PE_DATE_COLUMNS)
    value_column = _first_existing_column(frame, INDEX_PE_VALUE_COLUMNS)

    return [
        DailyMetric(
            "index",
            code,
            "rolling_pe",
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for _, row in frame.iterrows()
    ]


def normalize_index_dividend_yield_rows(code: str, frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, INDEX_PE_DATE_COLUMNS)
    value_column = _first_existing_column(frame, INDEX_DIVIDEND_YIELD_VALUE_COLUMNS)

    return [
        DailyMetric(
            "index",
            code,
            "dividend_yield",
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for _, row in frame.iterrows()
    ]


def normalize_sw_index_pb_rows(code: str, category: str, frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, SW_INDEX_DATE_COLUMNS)
    code_column = _first_existing_column(frame, SW_INDEX_CODE_COLUMNS)
    value_column = _first_existing_column(frame, SW_INDEX_PB_VALUE_COLUMNS)
    matched = frame[frame[code_column].astype(str) == str(code)]
    if matched.empty:
        raise DataSourceError(f"No PB data found for SW index {code} in {category}")

    return [
        DailyMetric(
            f"sw_index:{category}",
            code,
            "pb",
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for _, row in matched.iterrows()
    ]


def normalize_gold_rows(frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, GOLD_DATE_COLUMNS)
    value_column = _first_existing_column(frame, GOLD_CLOSE_COLUMNS)

    return [
        DailyMetric(
            "gold",
            "AU9999",
            "close",
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for _, row in frame.iterrows()
    ]


def normalize_cn10y_yield_rows(frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, CN10Y_YIELD_DATE_COLUMNS)
    value_column = _first_existing_column(frame, CN10Y_YIELD_VALUE_COLUMNS)

    rows = [
        row
        for _, row in frame.iterrows()
        if not _is_missing(row[date_column]) and not _is_missing(row[value_column])
    ]
    if not rows:
        raise DataSourceError("No valid CN10Y yield data")

    return [
        DailyMetric(
            "bond",
            "CN10Y",
            "yield",
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for row in rows
    ]


def _first_existing_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in frame.columns:
            return column

    raise DataSourceError(f"Missing expected columns: {', '.join(candidates)}")


def _to_iso_date(value: object) -> str:
    if _is_missing(value):
        raise DataSourceError(f"Invalid date value: {value!r}")
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    try:
        parsed = pd.to_datetime(value)
    except Exception as exc:
        raise DataSourceError(f"Invalid date value: {value!r}") from exc

    if _is_missing(parsed):
        raise DataSourceError(f"Invalid date value: {value!r}")

    return parsed.date().isoformat()


def _to_float(value: object) -> float:
    if _is_missing(value):
        raise DataSourceError(f"Invalid numeric value: {value!r}")

    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise DataSourceError(f"Invalid numeric value: {value!r}") from exc

    if _is_missing(parsed):
        raise DataSourceError(f"Invalid numeric value: {value!r}")

    return parsed


def _is_missing(value: object) -> bool:
    if isinstance(value, str) and not value.strip():
        return True

    try:
        return bool(pd.isna(value))
    except TypeError:
        return False
