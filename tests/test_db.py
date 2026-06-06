import pytest

from finance_cli.db import DailyMetric, FundInfo, MetricsRepository, SQLiteApiError


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


def test_repository_initialize_creates_fund_info_schema():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    repo.initialize()

    schema_sql = "\n".join(call[1]["sql"] for call in client.calls if call[0] == "/v1/sqlite/exec")
    assert "CREATE TABLE IF NOT EXISTS daily_metrics" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS fund_info" in schema_sql
    assert "purchase_fee_json TEXT NOT NULL" in schema_sql
    assert "redemption_fee_json TEXT NOT NULL" in schema_sql


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


def test_repository_upserts_fund_info():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    inserted = repo.upsert_fund_info(
        FundInfo(
            code="017763",
            name="银河领先债券C",
            fund_type="债券型",
            established_date="2023-01-01",
            asset_size="10.25亿元",
            purchase_status="开放申购",
            redemption_status="开放赎回",
            morningstar_rating="5",
            purchase_fee=[
                {
                    "min_amount": 0,
                    "max_amount": 1000000,
                    "original_rate": 0.015,
                    "discounted_rate": 0.0015,
                }
            ],
            redemption_fee=[
                {
                    "min_holding_days": 0,
                    "max_holding_days": 7,
                    "original_rate": 0.015,
                    "discounted_rate": 0.015,
                }
            ],
            source="manual",
            updated_at="2026-06-07T12:00:00+00:00",
        )
    )

    assert inserted == 1
    path, payload = client.calls[0]
    assert path == "/v1/sqlite/exec"
    assert payload["db"] == "finance.db"
    assert "INSERT INTO fund_info" in payload["sql"]
    assert "ON CONFLICT(code) DO UPDATE SET" in payload["sql"]
    assert payload["params"][0:9] == [
        "017763",
        "银河领先债券C",
        "债券型",
        "2023-01-01",
        "10.25亿元",
        "开放申购",
        "开放赎回",
        "5",
        '[{"min_amount":0,"max_amount":1000000,"original_rate":0.015,"discounted_rate":0.0015}]',
    ]
    assert payload["params"][9] == (
        '[{"min_holding_days":0,"max_holding_days":7,"original_rate":0.015,"discounted_rate":0.015}]'
    )
    assert payload["params"][10:12] == ["manual", "2026-06-07T12:00:00+00:00"]


def test_repository_deletes_metrics_for_single_series():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    deleted = repo.delete_metrics("index", "NDX", "rolling_pe")

    assert deleted == 1
    path, payload = client.calls[0]
    assert path == "/v1/sqlite/exec"
    assert payload["db"] == "finance.db"
    assert "DELETE FROM daily_metrics" in payload["sql"]
    assert payload["params"] == ["index", "NDX", "rolling_pe"]


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


def test_repository_queries_fund_info_by_code():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": {
                "columns": [
                    "code",
                    "name",
                    "fund_type",
                    "established_date",
                    "asset_size",
                    "purchase_status",
                    "redemption_status",
                    "morningstar_rating",
                    "purchase_fee_json",
                    "redemption_fee_json",
                    "source",
                    "updated_at",
                ],
                "rows": [
                    [
                        "017763",
                        "银河领先债券C",
                        "债券型",
                        "2023-01-01",
                        "10.25亿元",
                        "开放申购",
                        "开放赎回",
                        "5",
                        '[{"min_amount":0,"max_amount":1000000,"original_rate":0.015,"discounted_rate":0.0015}]',
                        '[{"min_holding_days":0,"max_holding_days":7,"original_rate":0.015,"discounted_rate":0.015}]',
                        "akshare",
                        "2026-06-07T12:00:00+00:00",
                    ]
                ],
                "row_count": 1,
            }
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    result = repo.fund_info_by_code("017763")

    assert result == FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            }
        ],
        redemption_fee=[
            {
                "min_holding_days": 0,
                "max_holding_days": 7,
                "original_rate": 0.015,
                "discounted_rate": 0.015,
            }
        ],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
    )
    assert client.calls[0][0] == "/v1/sqlite/query"
    assert client.calls[0][1]["params"] == ["017763"]


def test_repository_returns_none_for_missing_fund_info():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": {
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    assert repo.fund_info_by_code("017763") is None


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
