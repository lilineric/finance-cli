from finance_cli.db import DailyMetric
from finance_cli.service import MetricQueryResult, MetricsService


def fail_fetch():
    raise AssertionError("fetch_missing should not be called")


class InMemoryMetricsRepository:
    def __init__(self):
        self.rows = {}

    def initialize(self):
        pass

    def upsert_metrics(self, metrics):
        for metric in metrics:
            key = (metric.asset_type, metric.code, metric.metric, metric.date)
            self.rows[key] = metric
        return len(metrics)

    def delete_metrics(self, asset_type, code, metric):
        keys = [
            key
            for key, row in self.rows.items()
            if row.asset_type == asset_type and row.code == code and row.metric == metric
        ]
        for key in keys:
            del self.rows[key]
        return len(keys)

    def latest_date_on_or_before(self, asset_type, code, metric, query_date):
        dates = [
            row.date
            for row in self.rows.values()
            if row.asset_type == asset_type
            and row.code == code
            and row.metric == metric
            and row.date <= query_date
        ]
        return max(dates) if dates else None

    def metrics_between(self, asset_type, code, metric, start_date, end_date):
        return sorted(
            [
                row
                for row in self.rows.values()
                if row.asset_type == asset_type
                and row.code == code
                and row.metric == metric
                and start_date <= row.date <= end_date
            ],
            key=lambda row: row.date,
        )


def test_query_falls_back_to_previous_available_date_and_excludes_future_rows(tmp_path):
    repo = InMemoryMetricsRepository()
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


def test_replace_sync_deletes_existing_series_before_upserting_rows(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "NDX", "rolling_pe", "2026-05-01", 32.859, "worldperatio"),
            DailyMetric("index", "000300", "rolling_pe", "2026-05-22", 12.0, "akshare"),
        ]
    )

    count = service.replace_sync(
        "index",
        "NDX",
        "rolling_pe",
        lambda: [
            DailyMetric("index", "NDX", "rolling_pe", "2026-05-22", 35.1883, "danjuan"),
        ],
    )

    assert count == 1
    assert repo.rows == {
        ("index", "000300", "rolling_pe", "2026-05-22"): DailyMetric(
            "index",
            "000300",
            "rolling_pe",
            "2026-05-22",
            12.0,
            "akshare",
        ),
        ("index", "NDX", "rolling_pe", "2026-05-22"): DailyMetric(
            "index",
            "NDX",
            "rolling_pe",
            "2026-05-22",
            35.1883,
            "danjuan",
        ),
    }


def test_query_fetches_missing_data_before_calculating(tmp_path):
    repo = InMemoryMetricsRepository()
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
    repo = InMemoryMetricsRepository()
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
    repo = InMemoryMetricsRepository()
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


def test_query_accepts_lookback_start_on_next_trading_day(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "H30269", "rolling_pe", "2016-05-23", 8.0, "akshare"),
            DailyMetric("index", "H30269", "rolling_pe", "2026-05-22", 7.6, "akshare"),
        ]
    )

    result = service.query(
        asset_type="index",
        code="H30269",
        metric="rolling_pe",
        requested_date="2026-05-22",
        years=10,
        fetch_missing=fail_fetch,
        ensure_lookback_coverage=True,
    )

    assert result.sample_start_date == "2016-05-23"
    assert result.actual_date == "2026-05-22"


def test_query_uses_partial_coverage_when_minimum_lookback_is_available(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "990001", "rolling_pe", "2026-05-22", 120.0, "old"),
        ]
    )
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("index", "990001", "rolling_pe", "2020-02-27", 80.0, "akshare"),
            DailyMetric("index", "990001", "rolling_pe", "2026-05-22", 120.0, "akshare"),
        ]

    result = service.query(
        asset_type="index",
        code="990001",
        metric="rolling_pe",
        requested_date="2026-05-22",
        years=10,
        fetch_missing=fetch_missing,
        ensure_lookback_coverage=True,
        minimum_lookback_years=3,
    )

    assert calls == ["called"]
    assert result.actual_date == "2026-05-22"
    assert result.sample_start_date == "2020-02-27"
    assert result.value == 120.0
    assert result.percentile == 100.0
    assert result.sample_count == 2
    assert result.lookback_years == 10
    assert result.coverage_status == "partial"
    assert result.effective_years == 6.2


def test_query_raises_when_refreshed_lookback_coverage_is_still_incomplete(tmp_path):
    repo = InMemoryMetricsRepository()
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
            minimum_lookback_years=3,
        )
    except ValueError as exc:
        message = str(exc)
        assert "Sample coverage is incomplete" in message
        assert "expected_start_date=2016-05-21" in message
        assert "minimum_start_date=2023-05-21" in message
        assert "sample_start_date=2026-04-23" in message
        assert "sample_count=2" in message
    else:
        raise AssertionError("Expected ValueError")


def test_query_value_uses_exact_local_date_without_percentile_fields(tmp_path):
    repo = InMemoryMetricsRepository()
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


def test_query_value_uses_previous_fund_nav_when_local_history_covers_requested_date(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("fund", "017763", "unit_nav", "2026-05-22", 1.2456, "akshare"),
            DailyMetric("fund", "017763", "unit_nav", "2026-05-25", 1.2468, "akshare"),
        ]
    )

    result = service.query_value(
        asset_type="fund",
        code="017763",
        metric="unit_nav",
        requested_date="2026-05-23",
        fetch_missing=fail_fetch,
    )

    assert result.actual_date == "2026-05-22"
    assert result.value == 1.2456
    assert result.source == "akshare"


def test_query_value_backfills_fund_nav_history_before_returning_requested_date(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("fund", "017763", "unit_nav", "2026-05-21", 1.2345, "akshare"),
            DailyMetric("fund", "017763", "unit_nav", "2026-05-22", 1.2456, "akshare"),
            DailyMetric("fund", "017763", "unit_nav", "2026-05-26", 1.2512, "akshare"),
        ]

    result = service.query_value(
        asset_type="fund",
        code="017763",
        metric="unit_nav",
        requested_date="2026-05-23",
        fetch_missing=fetch_missing,
    )

    assert calls == ["called"]
    assert result.actual_date == "2026-05-22"
    assert result.value == 1.2456
    assert repo.metrics_between("fund", "017763", "unit_nav", "2026-05-01", "2026-05-31") == [
        DailyMetric("fund", "017763", "unit_nav", "2026-05-21", 1.2345, "akshare"),
        DailyMetric("fund", "017763", "unit_nav", "2026-05-22", 1.2456, "akshare"),
        DailyMetric("fund", "017763", "unit_nav", "2026-05-26", 1.2512, "akshare"),
    ]


def test_query_value_can_use_previous_local_date_without_fetching(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "930707", "pb", "2026-05-22", 2.2344, "etf.run"),
        ]
    )

    result = service.query_value(
        asset_type="index",
        code="930707",
        metric="pb",
        requested_date="2026-05-23",
        fetch_missing=fail_fetch,
        refresh_stale=False,
    )

    assert result.actual_date == "2026-05-22"
    assert result.value == 2.2344
    assert result.source == "etf.run"


def test_query_value_backfills_history_before_returning_previous_date(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("index", "930707", "pb", "2021-02-22", 3.299, "etf.run"),
            DailyMetric("index", "930707", "pb", "2026-05-22", 2.2344, "etf.run"),
        ]

    result = service.query_value(
        asset_type="index",
        code="930707",
        metric="pb",
        requested_date="2026-05-23",
        fetch_missing=fetch_missing,
        refresh_stale=False,
    )

    assert calls == ["called"]
    assert result.actual_date == "2026-05-22"
    assert result.value == 2.2344
    assert repo.metrics_between("index", "930707", "pb", "2021-01-01", "2026-12-31") == [
        DailyMetric("index", "930707", "pb", "2021-02-22", 3.299, "etf.run"),
        DailyMetric("index", "930707", "pb", "2026-05-22", 2.2344, "etf.run"),
    ]


def test_query_value_refreshes_stale_local_data(tmp_path):
    repo = InMemoryMetricsRepository()
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
    repo = InMemoryMetricsRepository()
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
    repo = InMemoryMetricsRepository()
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
    repo = InMemoryMetricsRepository()
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


def test_query_range_returns_rows_inside_requested_dates(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2025-12-31", 9.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-01-02", 10.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-01-05", 11.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-05-02", 12.0, "test"),
        ]
    )

    result = service.query_range(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_from="2026-01-01",
        requested_to="2026-05-01",
        fetch_missing=fail_fetch,
    )

    assert result.asset_type == "index"
    assert result.code == "000300"
    assert result.metric == "rolling_pe"
    assert result.requested_from == "2026-01-01"
    assert result.requested_to == "2026-05-01"
    assert result.actual_start_date == "2026-01-02"
    assert result.actual_end_date == "2026-01-05"
    assert result.data == [
        ("2026-01-02", 10.0, "test"),
        ("2026-01-05", 11.0, "test"),
    ]


def test_query_range_fetches_when_local_data_is_stale_for_end_date(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("gold", "AU9999", "close", "2026-01-02", 530.0, "old"),
        ]
    )
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("gold", "AU9999", "close", "2026-01-02", 531.0, "akshare"),
            DailyMetric("gold", "AU9999", "close", "2026-04-30", 540.0, "akshare"),
            DailyMetric("gold", "AU9999", "close", "2026-05-04", 545.0, "akshare"),
        ]

    result = service.query_range(
        asset_type="gold",
        code="AU9999",
        metric="close",
        requested_from="2026-01-01",
        requested_to="2026-05-01",
        fetch_missing=fetch_missing,
    )

    assert calls == ["called"]
    assert result.actual_start_date == "2026-01-02"
    assert result.actual_end_date == "2026-04-30"
    assert result.data == [
        ("2026-01-02", 531.0, "akshare"),
        ("2026-04-30", 540.0, "akshare"),
    ]


def test_query_range_raises_when_no_data_exists_after_fetch(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)

    try:
        service.query_range(
            asset_type="bond",
            code="CN10Y",
            metric="yield",
            requested_from="2026-01-01",
            requested_to="2026-05-01",
            fetch_missing=lambda: [
                DailyMetric("bond", "CN10Y", "yield", "2025-12-31", 1.8, "akshare"),
            ],
        )
    except ValueError as exc:
        assert "No data available for bond CN10Y yield between 2026-01-01 and 2026-05-01" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_query_range_rejects_from_after_to(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)

    try:
        service.query_range(
            asset_type="index",
            code="000300",
            metric="rolling_pe",
            requested_from="2026-05-01",
            requested_to="2026-01-01",
            fetch_missing=fail_fetch,
        )
    except ValueError as exc:
        assert "from date must be on or before to date" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
