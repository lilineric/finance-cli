from finance_cli.db import DailyMetric, MetricsRepository
from finance_cli.service import MetricQueryResult, MetricsService


def test_query_falls_back_to_previous_available_date_and_excludes_future_rows(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "pe_ttm", "2026-04-17", 10.0, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 20.0, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-21", 30.0, "test"),
        ]
    )

    result = service.query(
        asset_type="index",
        code="000300",
        metric="pe_ttm",
        requested_date="2026-04-19",
        years=1,
        fetch_missing=lambda: [],
    )

    assert result == MetricQueryResult(
        asset_type="index",
        code="000300",
        metric="pe_ttm",
        requested_date="2026-04-19",
        actual_date="2026-04-17",
        value=10.0,
        percentile=100.0,
        sample_count=1,
        source="test",
    )


def test_query_fetches_missing_data_before_calculating(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)

    result = service.query(
        asset_type="gold",
        code="AU9999",
        metric="close",
        requested_date="2026-04-20",
        years=1,
        fetch_missing=lambda: [
            DailyMetric("gold", "AU9999", "close", "2026-04-17", 530.0, "test"),
            DailyMetric("gold", "AU9999", "close", "2026-04-20", 540.0, "test"),
        ],
    )

    assert result.actual_date == "2026-04-20"
    assert result.value == 540.0
    assert result.percentile == 100.0
    assert result.sample_count == 2


def test_query_raises_when_no_data_exists_after_fetch(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)

    try:
        service.query(
            asset_type="index",
            code="000300",
            metric="pe_ttm",
            requested_date="2026-04-20",
            years=1,
            fetch_missing=lambda: [],
        )
    except ValueError as exc:
        assert "No data available" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
