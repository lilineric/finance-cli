from datetime import date, datetime, timedelta, timezone
from html import unescape
import json
from numbers import Integral, Real
import re
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from finance_cli.analytics import parse_query_date
from finance_cli.db import DailyMetric


INDEX_PE_DATE_COLUMNS = ("日期", "日期Date", "date", "trade_date")
INDEX_PE_VALUE_COLUMNS = ("滚动市盈率", "市盈率2（计算用股本）P/E2", "市盈率2", "市盈率TTM")
INDEX_DIVIDEND_YIELD_VALUE_COLUMNS = (
    "股息率2",
    "股息率2（计算用股本）D/P2",
    "股息率1",
    "股息率1（总股本）D/P1",
    "股息率",
    "dividend_yield",
)
SW_INDEX_DATE_COLUMNS = ("发布日期", "日期", "date", "trade_date")
SW_INDEX_CODE_COLUMNS = ("指数代码", "code", "index_code")
SW_INDEX_PB_VALUE_COLUMNS = ("市净率", "pb", "PB")
GOLD_DATE_COLUMNS = ("日期", "date", "trade_date")
GOLD_CLOSE_COLUMNS = ("收盘价", "close", "收盘")
CN10Y_YIELD_DATE_COLUMNS = ("日期", "date", "trade_date")
CN10Y_YIELD_VALUE_COLUMNS = ("中国国债收益率10年", "中国10年期国债收益率", "cn10y", "yield")
FUND_NAV_DATE_COLUMNS = ("净值日期", "日期", "date", "trade_date")
FUND_UNIT_NAV_VALUE_COLUMNS = ("单位净值", "unit_nav")
FUND_ACCUMULATED_NAV_VALUE_COLUMNS = ("累计净值", "accumulated_nav")
CSINDEX_HISTORY_START_DATE = "19900101"
DANJUAN_NDX_PE_URL = "https://danjuanfunds.com/djapi/index_eva/pe_history/NDX?day=all"
VN30_PE_URL = "https://worldperatio.com/area/vietnam/"
WORLDPERATIO_PE_BLOCK_PATTERN = re.compile(r"detailPE_data\s*=\s*(\[.*?\]);", re.DOTALL)
WORLDPERATIO_PE_DATA_PATTERN = re.compile(
    r"\[Date\.UTC\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2})\),\s*([0-9.]+)\]"
)
WORLDPERATIO_PE_URLS = {
    "VN30": VN30_PE_URL,
}
SHANGHAI_TZ = timezone(timedelta(hours=8))
ETF_RUN_CSI_INDEX_URL = "https://www.etf.run/index/CSI/{code}"
ETF_RUN_DATE_PATTERN = re.compile(r"更新至\s*(\d{4})/(\d{1,2})/(\d{1,2})")
ETF_RUN_PB_PATTERN = re.compile(r"最新市净率\s*([0-9.]+)")
FUND_NAV_TYPES = {
    "unit": ("unit_nav", "单位净值走势"),
    "accumulated": ("accumulated_nav", "累计净值走势"),
}


class DataSourceError(RuntimeError):
    pass


def fetch_index_pe_rows(code: str, fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    normalized_code = normalize_index_pe_code(code)
    if normalized_code == "NDX":
        try:
            text = fetcher() if fetcher is not None else _fetch_text(DANJUAN_NDX_PE_URL)
        except Exception as exc:
            raise DataSourceError(f"Failed to fetch index PE rows for {code}: {exc}") from exc
        return normalize_danjuan_index_pe_rows(normalized_code, text)

    if normalized_code in WORLDPERATIO_PE_URLS:
        try:
            html = fetcher() if fetcher is not None else _fetch_text(WORLDPERATIO_PE_URLS[normalized_code])
        except Exception as exc:
            raise DataSourceError(f"Failed to fetch index PE rows for {code}: {exc}") from exc
        return normalize_worldperatio_pe_rows(normalized_code, html)

    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.stock_zh_index_hist_csindex

    try:
        frame = fetcher(
            symbol=normalized_code,
            start_date=CSINDEX_HISTORY_START_DATE,
            end_date=date.today().strftime("%Y%m%d"),
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


def fetch_index_pb_rows(
    code: str,
    fetcher: Callable[[str], str] | None = None,
) -> list[DailyMetric]:
    normalized_code = normalize_csi_index_pb_code(code)
    url = ETF_RUN_CSI_INDEX_URL.format(code=normalized_code)
    try:
        html = fetcher(url) if fetcher is not None else _fetch_text(url)
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch index PB rows for {code}: {exc}") from exc
    return normalize_index_pb_rows_from_etf_run(normalized_code, html)


def normalize_csindex_code(code: str) -> str:
    normalized = code.strip().upper()
    if normalized.startswith(("SH", "SZ")):
        normalized = normalized[2:]
    if not re.fullmatch(r"(?:\d{6}|H\d{5})", normalized):
        raise DataSourceError(f"Invalid index code: {code}")
    return normalized


def normalize_csi_index_pb_code(code: str) -> str:
    normalized = code.strip().upper()
    if not re.fullmatch(r"9\d{5}", normalized):
        raise DataSourceError(
            f"PB without --category currently supports CSI 9xxxxx index codes only: {code}"
        )
    return normalized


def normalize_index_pe_code(code: str) -> str:
    normalized = code.strip().upper()
    if normalized == "NDX" or normalized in WORLDPERATIO_PE_URLS:
        return normalized
    return normalize_csindex_code(code)


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


def fetch_fund_nav_rows(
    code: str,
    nav_type: str = "unit",
    fetcher: Callable[..., pd.DataFrame] | None = None,
) -> list[DailyMetric]:
    normalized_code = normalize_fund_code(code)
    metric, indicator = _fund_nav_type_settings(nav_type)
    if fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional runtime environment
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc

        fetcher = ak.fund_open_fund_info_em

    try:
        frame = fetcher(symbol=normalized_code, indicator=indicator, period="成立来")
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch fund NAV rows for {code}: {exc}") from exc

    return normalize_fund_nav_rows(normalized_code, metric, frame)


def normalize_fund_code(code: str) -> str:
    normalized = code.strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise DataSourceError(f"Invalid fund code: {code}")
    return normalized


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
        if not _is_missing(row[value_column])
    ]


def normalize_ndx_pe_rows(html: str) -> list[DailyMetric]:
    try:
        return normalize_danjuan_index_pe_rows("NDX", html)
    except DataSourceError as exc:
        raise DataSourceError("No NDX PE data found") from exc


def normalize_danjuan_index_pe_rows(code: str, text: str) -> list[DailyMetric]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataSourceError(f"No Danjuan PE data found for {code}") from exc

    if payload.get("result_code") != 0:
        message = str(payload.get("message", "unknown error"))
        raise DataSourceError(f"Danjuan PE data request failed for {code}: {message}")

    series = payload.get("data", {}).get("index_eva_pe_growths")
    if not isinstance(series, list) or not series:
        raise DataSourceError(f"No Danjuan PE data found for {code}")

    rows = [
        DailyMetric(
            "index",
            code,
            "rolling_pe",
            _timestamp_ms_to_shanghai_date(point["ts"]),
            _to_float(point["pe"]),
            "danjuan",
        )
        for point in series
        if isinstance(point, dict) and "ts" in point and "pe" in point and not _is_missing(point["pe"])
    ]
    if not rows:
        raise DataSourceError(f"No Danjuan PE data found for {code}")
    return rows


def normalize_worldperatio_pe_rows(code: str, html: str) -> list[DailyMetric]:
    block_match = WORLDPERATIO_PE_BLOCK_PATTERN.search(html)
    if block_match is None:
        raise DataSourceError(f"No WorldPEratio PE data found for {code}")

    rows = [
        DailyMetric(
            "index",
            code,
            "rolling_pe",
            date(int(year), int(month_index) + 1, int(day)).isoformat(),
            _to_float(value),
            "worldperatio",
        )
        for year, month_index, day, value in WORLDPERATIO_PE_DATA_PATTERN.findall(block_match.group(1))
    ]
    if not rows:
        raise DataSourceError(f"No WorldPEratio PE data found for {code}")
    return rows


def _timestamp_ms_to_shanghai_date(value: object) -> str:
    return datetime.fromtimestamp(_to_float(value) / 1000, tz=SHANGHAI_TZ).date().isoformat()


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


def normalize_index_pb_rows_from_etf_run(code: str, html: str) -> list[DailyMetric]:
    compressed_rows = _normalize_index_pb_rows_from_etf_run_compressed_daily(code, html)
    if compressed_rows:
        return compressed_rows

    text = _html_to_text(html)
    date_match = ETF_RUN_DATE_PATTERN.search(text)
    value_match = ETF_RUN_PB_PATTERN.search(text)
    if date_match is None or value_match is None:
        raise DataSourceError(f"No index PB data found for {code}")

    year, month, day = date_match.groups()
    return [
        DailyMetric(
            "index",
            code,
            "pb",
            date(int(year), int(month), int(day)).isoformat(),
            _to_float(value_match.group(1)),
            "etf.run",
        )
    ]


def _normalize_index_pb_rows_from_etf_run_compressed_daily(code: str, html: str) -> list[DailyMetric]:
    text = html.replace(r"\"", '"')
    marker_index = text.find('"compressedIndexDaily"')
    if marker_index == -1:
        return []

    try:
        field_names = json.loads(_json_array_after(text, '"fieldNames"', marker_index))
        values = json.loads(_json_array_after(text, '"values"', marker_index))
        date_index = field_names.index("date")
        value_index = field_names.index("equalWeightedPbTtm")
    except (json.JSONDecodeError, ValueError) as exc:
        raise DataSourceError(f"No index PB history data found for {code}") from exc

    rows = [
        DailyMetric(
            "index",
            code,
            "pb",
            _to_iso_date(row[date_index]),
            _to_float(row[value_index]),
            "etf.run",
        )
        for row in values
        if len(row) > value_index and not _is_missing(row[value_index])
    ]
    if not rows:
        raise DataSourceError(f"No index PB history data found for {code}")
    return rows


def _json_array_after(text: str, marker: str, start: int) -> str:
    marker_index = text.find(marker, start)
    if marker_index == -1:
        raise ValueError(f"Missing marker: {marker}")
    array_start = text.find("[", marker_index + len(marker))
    if array_start == -1:
        raise ValueError(f"Missing array after marker: {marker}")

    depth = 0
    in_string = False
    escape = False
    for index in range(array_start, len(text)):
        character = text[index]
        if in_string:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
        else:
            if character == '"':
                in_string = True
            elif character == "[":
                depth += 1
            elif character == "]":
                depth -= 1
                if depth == 0:
                    return text[array_start : index + 1]

    raise ValueError(f"Unterminated array after marker: {marker}")


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


def normalize_fund_nav_rows(code: str, metric: str, frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, FUND_NAV_DATE_COLUMNS)
    value_column = _first_existing_column(frame, _fund_nav_value_columns(metric))

    rows = [
        DailyMetric(
            "fund",
            code,
            metric,
            _to_iso_date(row[date_column]),
            _to_float(row[value_column]),
            "akshare",
        )
        for _, row in frame.iterrows()
        if not _is_missing(row[value_column])
    ]
    if not rows:
        raise DataSourceError(f"No fund NAV data found for {code}")
    return rows


def _fund_nav_type_settings(nav_type: str) -> tuple[str, str]:
    try:
        return FUND_NAV_TYPES[nav_type]
    except KeyError as exc:
        raise DataSourceError(f"Invalid fund NAV type: {nav_type}") from exc


def _fund_nav_value_columns(metric: str) -> tuple[str, ...]:
    if metric == "unit_nav":
        return FUND_UNIT_NAV_VALUE_COLUMNS
    if metric == "accumulated_nav":
        return FUND_ACCUMULATED_NAV_VALUE_COLUMNS
    raise DataSourceError(f"Invalid fund NAV metric: {metric}")


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
    if isinstance(value, Integral) and re.fullmatch(r"\d{8}", str(value)):
        return datetime.strptime(str(value), "%Y%m%d").date().isoformat()
    if isinstance(value, Real) and float(value).is_integer():
        date_text = str(int(value))
        if re.fullmatch(r"\d{8}", date_text):
            return datetime.strptime(date_text, "%Y%m%d").date().isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{8}", value.strip()):
        return datetime.strptime(value.strip(), "%Y%m%d").date().isoformat()

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


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 500 and body:
            return body
        raise


def _html_to_text(html: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text))
