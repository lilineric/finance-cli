from finance_cli.db import DailyMetric, MetricsRepository
from finance_cli.service import MetricQueryResult, MetricsService


def fail_fetch():
    raise AssertionError("fetch_missing should not be called")


def test_query_falls_back_to_previous_available_date_and_excludes_future_rows(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2026-04-17", 10.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-04-20", 20.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-04-21", 30.0, "test"),
        ]
    )

    result = service.query(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_date="2026-04-19",
        years=1,
        fetch_missing=fail_fetch,
    )

    assert result == MetricQueryResult(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_date="2026-04-19",
        actual_date="2026-04-17",
        sample_start_date="2026-04-17",
        value=10.0,
        percentile=100.0,
        sample_count=1,
        source="test",
        lookback_years=1,
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
    assert result.sample_start_date == "2026-04-17"
    assert result.value == 540.0
    assert result.percentile == 100.0
    assert result.sample_count == 2
    assert result.lookback_years == 1


def test_query_uses_exact_local_date_without_fetching(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2026-04-17", 10.0, "local"),
            DailyMetric("index", "000300", "rolling_pe", "2026-04-20", 20.0, "local"),
        ]
    )

    result = service.query(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_date="2026-04-20",
        years=1,
        fetch_missing=fail_fetch,
    )

    assert result.actual_date == "2026-04-20"
    assert result.sample_start_date == "2026-04-17"
    assert result.value == 20.0
    assert result.sample_count == 2


def test_query_can_refresh_when_local_lookback_coverage_is_incomplete(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2026-04-23", 18.0, "old"),
            DailyMetric("index", "000300", "rolling_pe", "2026-05-21", 17.22, "old"),
        ]
    )
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("index", "000300", "rolling_pe", "2016-05-21", 10.0, "akshare"),
            DailyMetric("index", "000300", "rolling_pe", "2026-04-23", 15.0, "akshare"),
            DailyMetric("index", "000300", "rolling_pe", "2026-05-21", 14.42, "akshare"),
        ]

    result = service.query(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_date="2026-05-21",
        years=10,
        fetch_missing=fetch_missing,
        ensure_lookback_coverage=True,
    )

    assert calls == ["called"]
    assert result.actual_date == "2026-05-21"
    assert result.sample_start_date == "2016-05-21"
    assert result.value == 14.42
    assert result.sample_count == 3
    assert result.source == "akshare"


def test_query_raises_when_refreshed_lookback_coverage_is_still_incomplete(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "dividend_yield", "2026-04-23", 2.1, "old"),
            DailyMetric("index", "000300", "dividend_yield", "2026-05-21", 2.32, "old"),
        ]
    )

    try:
        service.query(
            asset_type="index",
            code="000300",
            metric="dividend_yield",
            requested_date="2026-05-22",
            years=10,
            fetch_missing=lambda: [
                DailyMetric("index", "000300", "dividend_yield", "2026-04-23", 2.1, "akshare"),
                DailyMetric("index", "000300", "dividend_yield", "2026-05-21", 2.32, "akshare"),
            ],
            ensure_lookback_coverage=True,
        )
    except ValueError as exc:
        message = str(exc)
        assert "Sample coverage is incomplete" in message
        assert "expected_start_date=2016-05-21" in message
        assert "sample_start_date=2026-04-23" in message
        assert "sample_count=2" in message
    else:
        raise AssertionError("Expected ValueError")


def test_query_value_uses_exact_local_date_without_percentile_fields(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "dividend_yield", "2026-04-23", 2.1, "akshare"),
            DailyMetric("index", "000300", "dividend_yield", "2026-05-21", 2.32, "akshare"),
        ]
    )

    result = service.query_value(
        asset_type="index",
        code="000300",
        metric="dividend_yield",
        requested_date="2026-05-21",
        fetch_missing=fail_fetch,
    )

    assert result.actual_date == "2026-05-21"
    assert result.value == 2.32
    assert result.percentile is None
    assert result.sample_start_date is None
    assert result.sample_count is None
    assert result.lookback_years is None


def test_query_value_refreshes_stale_local_data(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("sw_index:一级行业", "801010", "pb", "2026-04-17", 1.7, "old"),
        ]
    )
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("sw_index:一级行业", "801010", "pb", "2026-04-20", 1.8, "akshare"),
            DailyMetric("sw_index:一级行业", "801010", "pb", "2026-04-21", 1.9, "akshare"),
        ]

    result = service.query_value(
        asset_type="sw_index:一级行业",
        code="801010",
        metric="pb",
        requested_date="2026-04-20",
        fetch_missing=fetch_missing,
    )

    assert calls == ["called"]
    assert result.actual_date == "2026-04-20"
    assert result.value == 1.8
    assert result.source == "akshare"


def test_query_refreshes_stale_local_data_and_excludes_future_rows(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2026-04-17", 10.0, "local"),
        ]
    )

    result = service.query(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_date="2026-04-20",
        years=1,
        fetch_missing=lambda: [
            DailyMetric("index", "000300", "rolling_pe", "2026-04-20", 20.0, "remote"),
            DailyMetric("index", "000300", "rolling_pe", "2026-04-21", 30.0, "remote"),
        ],
    )

    assert result.actual_date == "2026-04-20"
    assert result.sample_start_date == "2026-04-17"
    assert result.value == 20.0
    assert result.percentile == 100.0
    assert result.sample_count == 2


def test_sync_initializes_repository_and_returns_upsert_count(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    calls = []

    def fetch_rows():
        calls.append("called")
        return [
            DailyMetric("gold", "AU9999", "close", "2026-04-20", 540.0, "test"),
        ]

    count = service.sync(fetch_rows)

    assert count == 1
    assert calls == ["called"]
    assert (
        repo.latest_date_on_or_before("gold", "AU9999", "close", "2026-04-20") == "2026-04-20"
    )


def test_query_raises_when_no_data_exists_after_fetch(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)

    try:
        service.query(
            asset_type="index",
            code="000300",
            metric="rolling_pe",
            requested_date="2026-04-20",
            years=1,
            fetch_missing=lambda: [],
        )
    except ValueError as exc:
        assert "No data available" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
