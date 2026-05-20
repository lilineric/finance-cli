from finance_cli.db import DailyMetric, MetricsRepository


def test_repository_upserts_and_queries_latest_date(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "pe_ttm", "2026-04-17", 12.3, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 12.8, "test"),
        ]
    )

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
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    repo.upsert_metrics([DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 12.8, "first")])
    repo.upsert_metrics([DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 13.1, "second")])

    rows = repo.metrics_between("index", "000300", "pe_ttm", "2026-04-20", "2026-04-20")

    assert len(rows) == 1
    assert rows[0].value == 13.1
    assert rows[0].source == "second"
