from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class DailyMetric:
    asset_type: str
    code: str
    metric: str
    date: str
    value: float
    source: str


@dataclass(frozen=True)
class FundInfo:
    code: str
    name: str
    fund_type: str | None
    established_date: str | None
    asset_size: str | None
    purchase_status: str | None
    redemption_status: str | None
    morningstar_rating: str | None
    purchase_fee: list[dict[str, Any]]
    redemption_fee: list[dict[str, Any]]
    source: str
    updated_at: str


class SQLiteApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"SQLite API error ({status_code} {code}): {message}")


class SQLiteApiClient:
    def __init__(self, api_host: str, timeout: float = 30.0) -> None:
        self.api_host = api_host.rstrip("/")
        self.timeout = timeout

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.api_host}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return _decode_json_response(response.read())
        except HTTPError as exc:
            raise _api_error_from_http_error(exc) from exc
        except URLError as exc:
            raise SQLiteApiError(0, "connection_error", str(exc.reason)) from exc


class MetricsRepository:
    def __init__(
        self,
        api_host: str,
        db_name: str,
        client: SQLiteApiClient | None = None,
    ) -> None:
        self.db_name = db_name
        self.client = client or SQLiteApiClient(api_host)

    def initialize(self) -> None:
        try:
            self.client.post_json(
                "/v1/sqlite/db/create",
                {"db": self.db_name, "description": "finance-cli metrics database"},
            )
        except SQLiteApiError as exc:
            if not (exc.status_code == 409 and exc.code == "conflict"):
                raise

        self.client.post_json(
            "/v1/sqlite/exec",
            {
                "db": self.db_name,
                "sql": """
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    asset_type TEXT NOT NULL,
                    code TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    date TEXT NOT NULL,
                    value REAL NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (asset_type, code, metric, date)
                )
                """,
                "params": [],
            },
        )

        self.client.post_json(
            "/v1/sqlite/exec",
            {
                "db": self.db_name,
                "sql": """
                CREATE TABLE IF NOT EXISTS fund_info (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    fund_type TEXT,
                    established_date TEXT,
                    asset_size TEXT,
                    purchase_status TEXT,
                    redemption_status TEXT,
                    morningstar_rating TEXT,
                    purchase_fee_json TEXT NOT NULL,
                    redemption_fee_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                "params": [],
            },
        )

    def upsert_metrics(self, metrics: list[DailyMetric]) -> int:
        if not metrics:
            return 0

        updated_at = datetime.now(UTC).isoformat()
        for chunk in _chunks(metrics, 250):
            values_sql = ", ".join(["(?, ?, ?, ?, ?, ?, ?)"] * len(chunk))
            params: list[str | float] = []
            for metric in chunk:
                params.extend(
                    [
                        metric.asset_type,
                        metric.code,
                        metric.metric,
                        metric.date,
                        metric.value,
                        metric.source,
                        updated_at,
                    ]
                )
            self.client.post_json(
                "/v1/sqlite/exec",
                {
                    "db": self.db_name,
                    "sql": f"""
                    INSERT INTO daily_metrics (asset_type, code, metric, date, value, source, updated_at)
                    VALUES {values_sql}
                    ON CONFLICT(asset_type, code, metric, date) DO UPDATE SET
                        value = excluded.value,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    "params": params,
                },
            )

        return len(metrics)

    def delete_metrics(self, asset_type: str, code: str, metric: str) -> int:
        response = self.client.post_json(
            "/v1/sqlite/exec",
            {
                "db": self.db_name,
                "sql": """
                DELETE FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                """,
                "params": [asset_type, code, metric],
            },
        )
        return int(response.get("rows_affected", 0))

    def latest_date_on_or_before(
        self,
        asset_type: str,
        code: str,
        metric: str,
        query_date: str,
    ) -> str | None:
        response = self.client.post_json(
            "/v1/sqlite/query",
            {
                "db": self.db_name,
                "sql": """
                SELECT date
                FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                  AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                "params": [asset_type, code, metric, query_date],
            },
        )
        rows = response.get("rows", [])

        return rows[0][0] if rows else None

    def metrics_between(
        self,
        asset_type: str,
        code: str,
        metric: str,
        start_date: str,
        end_date: str,
    ) -> list[DailyMetric]:
        response = self.client.post_json(
            "/v1/sqlite/query",
            {
                "db": self.db_name,
                "sql": """
                SELECT asset_type, code, metric, date, value, source
                FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                  AND date BETWEEN ? AND ?
                ORDER BY date ASC
                """,
                "params": [asset_type, code, metric, start_date, end_date],
            },
        )

        columns = response.get("columns", [])
        return [DailyMetric(**dict(zip(columns, row, strict=True))) for row in response.get("rows", [])]

    def upsert_fund_info(self, fund_info: FundInfo) -> int:
        response = self.client.post_json(
            "/v1/sqlite/exec",
            {
                "db": self.db_name,
                "sql": """
                INSERT INTO fund_info (
                    code,
                    name,
                    fund_type,
                    established_date,
                    asset_size,
                    purchase_status,
                    redemption_status,
                    morningstar_rating,
                    purchase_fee_json,
                    redemption_fee_json,
                    source,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    fund_type = excluded.fund_type,
                    established_date = excluded.established_date,
                    asset_size = excluded.asset_size,
                    purchase_status = excluded.purchase_status,
                    redemption_status = excluded.redemption_status,
                    morningstar_rating = excluded.morningstar_rating,
                    purchase_fee_json = excluded.purchase_fee_json,
                    redemption_fee_json = excluded.redemption_fee_json,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                "params": [
                    fund_info.code,
                    fund_info.name,
                    fund_info.fund_type,
                    fund_info.established_date,
                    fund_info.asset_size,
                    fund_info.purchase_status,
                    fund_info.redemption_status,
                    fund_info.morningstar_rating,
                    _compact_json(fund_info.purchase_fee),
                    _compact_json(fund_info.redemption_fee),
                    fund_info.source,
                    fund_info.updated_at,
                ],
            },
        )
        return int(response.get("rows_affected", 0))

    def fund_info_by_code(self, code: str) -> FundInfo | None:
        response = self.client.post_json(
            "/v1/sqlite/query",
            {
                "db": self.db_name,
                "sql": """
                SELECT
                    code,
                    name,
                    fund_type,
                    established_date,
                    asset_size,
                    purchase_status,
                    redemption_status,
                    morningstar_rating,
                    purchase_fee_json,
                    redemption_fee_json,
                    source,
                    updated_at
                FROM fund_info
                WHERE code = ?
                LIMIT 1
                """,
                "params": [code],
            },
        )
        rows = response.get("rows", [])
        if not rows:
            return None

        columns = response.get("columns", [])
        row = dict(zip(columns, rows[0], strict=True))
        return FundInfo(
            code=str(row["code"]),
            name=str(row["name"]),
            fund_type=_optional_str(row["fund_type"]),
            established_date=_optional_str(row["established_date"]),
            asset_size=_optional_str(row["asset_size"]),
            purchase_status=_optional_str(row["purchase_status"]),
            redemption_status=_optional_str(row["redemption_status"]),
            morningstar_rating=_optional_str(row["morningstar_rating"]),
            purchase_fee=_decode_json_list(row["purchase_fee_json"]),
            redemption_fee=_decode_json_list(row["redemption_fee_json"]),
            source=str(row["source"]),
            updated_at=str(row["updated_at"]),
        )


def _decode_json_response(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode_json_list(value: Any) -> list[dict[str, Any]]:
    decoded = json.loads(str(value))
    if not isinstance(decoded, list):
        raise ValueError("stored fund fee JSON must be a list")
    return decoded


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _api_error_from_http_error(exc: HTTPError) -> SQLiteApiError:
    try:
        payload = _decode_json_response(exc.read())
        error = payload.get("error", {})
        code = str(error.get("code", "http_error"))
        message = str(error.get("message", exc.reason))
    except (json.JSONDecodeError, UnicodeDecodeError):
        code = "http_error"
        message = str(exc.reason)
    return SQLiteApiError(exc.code, code, message)


def _chunks(metrics: list[DailyMetric], size: int) -> list[list[DailyMetric]]:
    return [metrics[index : index + size] for index in range(0, len(metrics), size)]
