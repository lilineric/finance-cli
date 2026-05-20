import sqlite3

from finance_cli.db import DailyMetric, MetricsRepository


def test_repository_upserts_and_queries_latest_date(tmp_path):
    db_path = tmp_path / "nested" / "finance.db"
    repo = MetricsRepository(db_path)
    repo.initialize()

    assert db_path.exists()
    assert repo.upsert_metrics([]) == 0
    assert repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "pe_ttm", "2026-04-17", 12.3, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 12.8, "test"),
        ]
    ) == 2

    assert repo.latest_date_on_or_before("index", "000300", "pe_ttm", "2026-04-19") == "2026-04-17"


def test_repository_range_query_excludes_future_rows(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    repo.upsert_metrics(
        [
            DailyMetric("gold", "AU9999", "close", "2026-04-18", 530.0, "test"),
            DailyMetric("gold", "AU9999", "close", "2026-04-20", 540.0, "test"),
            DailyMetric("gold", "AU9999", "close", "2026-04-21", 550.0, "test"),
        ]
    )

    rows = repo.metrics_between("gold", "AU9999", "close", "2026-04-01", "2026-04-20")

    assert [row.date for row in rows] == ["2026-04-18", "2026-04-20"]
    assert [row.value for row in rows] == [530.0, 540.0]


def test_repository_upsert_replaces_existing_value(tmp_path):
    db_path = tmp_path / "finance.db"
    repo = MetricsRepository(db_path)
    repo.initialize()

    repo.upsert_metrics([DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 12.8, "first")])
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE daily_metrics
            SET updated_at = ?
            WHERE asset_type = ? AND code = ? AND metric = ? AND date = ?
            """,
            ("old-timestamp", "index", "000300", "pe_ttm", "2026-04-20"),
        )

    repo.upsert_metrics([DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 13.1, "second")])

    rows = repo.metrics_between("index", "000300", "pe_ttm", "2026-04-20", "2026-04-20")

    assert len(rows) == 1
    assert rows[0].value == 13.1
    assert rows[0].source == "second"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT updated_at
            FROM daily_metrics
            WHERE asset_type = ? AND code = ? AND metric = ? AND date = ?
            """,
            ("index", "000300", "pe_ttm", "2026-04-20"),
        ).fetchone()

    assert row[0]
    assert row[0] != "old-timestamp"
    assert row[0].endswith("+00:00")


def test_repository_schema_includes_updated_at(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    with sqlite3.connect(tmp_path / "finance.db") as conn:
        columns = {
            row[1]: {"type": row[2], "not_null": row[3]}
            for row in conn.execute("PRAGMA table_info(daily_metrics)")
        }

    assert columns["updated_at"] == {"type": "TEXT", "not_null": 1}
