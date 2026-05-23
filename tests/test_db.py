import pytest

from finance_cli.db import DailyMetric, MetricsRepository, SQLiteApiError


class FakeSQLiteApiClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def post_json(self, path, payload):
        self.calls.append((path, payload))
        response = self.responses.get(path)
        if isinstance(response, Exception):
            raise response
        if response is not None:
            return response
        if path == "/v1/sqlite/exec":
            return {"rows_affected": 1, "last_insert_id": 0}
        return {}


def test_repository_initialize_creates_database_and_schema():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    repo.initialize()

    assert client.calls[0] == (
        "/v1/sqlite/db/create",
        {"db": "finance.db", "description": "finance-cli metrics database"},
    )
    assert client.calls[1][0] == "/v1/sqlite/exec"
    assert client.calls[1][1]["db"] == "finance.db"
    assert "CREATE TABLE IF NOT EXISTS daily_metrics" in client.calls[1][1]["sql"]


def test_repository_initialize_treats_existing_database_as_success():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/db/create": SQLiteApiError(
                409,
                "conflict",
                "database already exists",
            )
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    repo.initialize()

    assert client.calls[-1][0] == "/v1/sqlite/exec"


def test_repository_upserts_metrics_with_single_exec_request():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    assert repo.upsert_metrics([]) == 0
    assert repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2026-04-17", 12.3, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-04-20", 12.8, "test"),
        ]
    ) == 2

    path, payload = client.calls[0]
    assert path == "/v1/sqlite/exec"
    assert payload["db"] == "finance.db"
    assert payload["sql"].count("(?, ?, ?, ?, ?, ?, ?)") == 2
    assert "ON CONFLICT(asset_type, code, metric, date) DO UPDATE SET" in payload["sql"]
    assert payload["params"][:6] == [
        "index",
        "000300",
        "rolling_pe",
        "2026-04-17",
        12.3,
        "test",
    ]
    assert payload["params"][7:13] == [
        "index",
        "000300",
        "rolling_pe",
        "2026-04-20",
        12.8,
        "test",
    ]
    assert payload["params"][6].endswith("+00:00")
    assert payload["params"][13] == payload["params"][6]


def test_repository_queries_latest_date():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": {
                "columns": ["date"],
                "rows": [["2026-04-17"]],
                "row_count": 1,
            }
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    result = repo.latest_date_on_or_before("index", "000300", "rolling_pe", "2026-04-19")

    assert result == "2026-04-17"
    assert client.calls[0][0] == "/v1/sqlite/query"
    assert client.calls[0][1]["params"] == ["index", "000300", "rolling_pe", "2026-04-19"]


def test_repository_range_query_maps_rows_to_daily_metrics():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": {
                "columns": ["asset_type", "code", "metric", "date", "value", "source"],
                "rows": [
                    ["gold", "AU9999", "close", "2026-04-18", 530.0, "test"],
                    ["gold", "AU9999", "close", "2026-04-20", 540.0, "test"],
                ],
                "row_count": 2,
            }
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    rows = repo.metrics_between("gold", "AU9999", "close", "2026-04-01", "2026-04-20")

    assert rows == [
        DailyMetric("gold", "AU9999", "close", "2026-04-18", 530.0, "test"),
        DailyMetric("gold", "AU9999", "close", "2026-04-20", 540.0, "test"),
    ]
    assert client.calls[0][1]["params"] == [
        "gold",
        "AU9999",
        "close",
        "2026-04-01",
        "2026-04-20",
    ]


def test_repository_raises_api_errors():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": SQLiteApiError(
                500,
                "sqlite_error",
                "database is locked",
            )
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    with pytest.raises(SQLiteApiError, match="database is locked"):
        repo.metrics_between("gold", "AU9999", "close", "2026-04-01", "2026-04-20")
