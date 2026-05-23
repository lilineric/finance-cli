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


def _decode_json_response(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


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
