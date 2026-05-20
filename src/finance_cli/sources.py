from datetime import date, datetime
from typing import Callable

import pandas as pd

from finance_cli.db import DailyMetric


INDEX_PE_DATE_COLUMNS = ("日期", "date", "trade_date")
INDEX_PE_VALUE_COLUMNS = ("市盈率2", "市盈率1", "滚动市盈率", "市盈率TTM", "pe_ttm", "PE_TTM")
GOLD_DATE_COLUMNS = ("日期", "date", "trade_date")
GOLD_CLOSE_COLUMNS = ("收盘价", "close", "收盘")


class DataSourceError(RuntimeError):
    pass


def fetch_index_pe_rows(code: str, fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.stock_zh_index_value_csindex

    try:
        frame = fetcher(symbol=code)
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch index PE rows for {code}: {exc}") from exc

    return normalize_index_pe_rows(code, frame)


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


def normalize_index_pe_rows(code: str, frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, INDEX_PE_DATE_COLUMNS)
    value_column = _first_existing_column(frame, INDEX_PE_VALUE_COLUMNS)

    return [
        DailyMetric(
            "index",
            code,
            "pe_ttm",
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for _, row in frame.iterrows()
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
