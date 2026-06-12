import pytest

from finance_cli.db import DailyMetric, FundInfo, OperationFee
from finance_cli.service import MetricQueryResult, MetricsService
from finance_cli.sources import DataSourceError, compute_erp_rows


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


class FakeFundInfoRepository:
    def __init__(self, existing=None, by_code=None):
        self.existing = existing
        self.by_code = by_code
        self.initialize_calls = 0
        self.query_calls = []
        self.upserts = []

    def initialize(self):
        self.initialize_calls += 1

    def fund_info_by_code(self, code):
        self.query_calls.append(code)
        if self.by_code is not None:
            return self.by_code.get(code)
        return self.existing

    def fund_info_codes(self):
        if self.by_code is not None:
            return list(self.by_code)
        if self.existing is None:
            return []
        return [self.existing.code]

    def upsert_fund_info(self, fund_info):
        self.existing = fund_info
        if self.by_code is not None:
            self.by_code[fund_info.code] = fund_info
        self.upserts.append(fund_info)
        return 1


def _fund_info(
    code="017763",
    name="银河领先债券C",
    source="akshare",
    updated_at="2026-06-07T12:00:00+00:00",
    operation_fee=OperationFee(),
    purchase_status="开放申购",
    purchase_limit_amount=0,
    redemption_status="开放赎回",
    purchase_fee=None,
    redemption_fee=None,
):
    return FundInfo(
        code=code,
        name=name,
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        operation_fee=operation_fee,
        purchase_status=purchase_status,
        purchase_limit_amount=purchase_limit_amount,
        redemption_status=redemption_status,
        morningstar_rating="5",
        purchase_fee=[] if purchase_fee is None else purchase_fee,
        redemption_fee=[] if redemption_fee is None else redemption_fee,
        source=source,
        updated_at=updated_at,
    )


def test_query_fund_info_returns_cached_data_without_fetching():
    cached = _fund_info(source="manual")
    repo = FakeFundInfoRepository(existing=cached)
    service = MetricsService(repo)
    called = False

    def fetch_missing():
        nonlocal called
        called = True
        return _fund_info()

    result = service.query_fund_info("017763", fetch_missing)

    assert result == cached
    assert called is False
    assert repo.initialize_calls == 1
    assert repo.upserts == []


def test_query_fund_info_fetches_and_upserts_when_cache_missing():
    repo = FakeFundInfoRepository(existing=None)
    service = MetricsService(repo)
    fresh = _fund_info()

    result = service.query_fund_info("017763", lambda: fresh)

    assert result == fresh
    assert repo.upserts == [fresh]


def test_query_fund_info_refresh_fetches_even_when_cache_exists():
    cached = _fund_info(source="manual")
    fresh = _fund_info(source="akshare", updated_at="2026-06-07T13:00:00+00:00")
    repo = FakeFundInfoRepository(existing=cached)
    service = MetricsService(repo)

    result = service.query_fund_info("017763", lambda: fresh, refresh=True)

    assert result == fresh
    assert repo.upserts == [fresh]


def test_query_fund_info_returns_cached_data_when_default_fetch_fails():
    cached = _fund_info(source="manual")
    repo = FakeFundInfoRepository(existing=cached)
    repo.existing = None
    service = MetricsService(repo)

    def fetch_missing():
        repo.existing = cached
        raise DataSourceError("akshare unavailable")

    result = service.query_fund_info("017763", fetch_missing)

    assert result == cached
    assert repo.upserts == []


def test_query_fund_info_refresh_fetch_failure_does_not_return_cached_data():
    cached = _fund_info(source="manual")
    repo = FakeFundInfoRepository(existing=cached)
    service = MetricsService(repo)

    def fetch_missing():
        raise DataSourceError("akshare unavailable")

    with pytest.raises(DataSourceError, match="akshare unavailable"):
        service.query_fund_info("017763", fetch_missing, refresh=True)

    assert repo.upserts == []


def test_update_fund_info_initializes_and_upserts():
    fund_info = _fund_info(source="manual")
    repo = FakeFundInfoRepository()
    service = MetricsService(repo)

    result = service.update_fund_info(fund_info)

    assert result == fund_info
    assert repo.initialize_calls == 1
    assert repo.upserts == [fund_info]


def test_sync_fund_info_refreshes_codes_and_records_important_changes():
    cached = _fund_info(
        operation_fee=OperationFee(
            management_fee=0.003,
            custodian_fee=0.001,
            sales_service_fee=0.0,
        ),
        purchase_status="开放申购",
        purchase_limit_amount=None,
        purchase_fee=[],
    )
    fresh = _fund_info(
        operation_fee=OperationFee(
            management_fee=0.004,
            custodian_fee=0.001,
            sales_service_fee=0.0,
        ),
        purchase_status="暂停申购",
        purchase_limit_amount=0,
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": None,
                "original_rate": 0.0,
                "discounted_rate": 0.0,
            }
        ],
        updated_at="2026-06-08T12:00:00+00:00",
    )
    repo = FakeFundInfoRepository(by_code={"017763": cached})
    service = MetricsService(repo)

    result = service.sync_fund_info(lambda code: fresh, max_workers=1)

    assert result.total == 1
    assert result.updated == 1
    assert result.unchanged == 0
    assert result.failures == []
    assert repo.upserts == [fresh]
    assert {change.field for change in result.successes[0].changes} == {
        "operation_fee.management_fee",
        "purchase_status",
        "purchase_limit_amount",
        "purchase_fee",
    }


def test_sync_fund_info_ignores_non_important_changes():
    cached = _fund_info(name="旧名称", source="manual")
    fresh = _fund_info(name="新名称", source="akshare", updated_at="2026-06-08T12:00:00+00:00")
    repo = FakeFundInfoRepository(by_code={"017763": cached})
    service = MetricsService(repo)

    result = service.sync_fund_info(lambda code: fresh, max_workers=1)

    assert result.total == 1
    assert result.updated == 1
    assert result.unchanged == 1
    assert result.successes[0].changes == []


def test_sync_fund_info_continues_after_single_fetch_failure():
    first = _fund_info(code="017763")
    second = _fund_info(code="008887", name="华夏国证半导体芯片ETF联接A")
    fresh_second = _fund_info(
        code="008887",
        name="华夏国证半导体芯片ETF联接A",
        redemption_status="暂停赎回",
    )
    repo = FakeFundInfoRepository(by_code={"017763": first, "008887": second})
    service = MetricsService(repo)

    def fetcher(code):
        if code == "017763":
            raise DataSourceError("source failed")
        return fresh_second

    result = service.sync_fund_info(fetcher, max_workers=1)

    assert result.total == 2
    assert result.updated == 1
    assert repo.upserts == [fresh_second]
    assert [(failure.code, failure.error) for failure in result.failures] == [
        ("017763", "source failed")
    ]
    assert result.successes[0].code == "008887"


def test_sync_fund_info_empty_table_does_not_fetch():
    repo = FakeFundInfoRepository(by_code={})
    service = MetricsService(repo)
    called = False

    def fetcher(code):
        nonlocal called
        called = True
        return _fund_info(code=code)

    result = service.sync_fund_info(fetcher, max_workers=1)

    assert result.total == 0
    assert result.updated == 0
    assert result.failures == []
    assert called is False


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


def test_query_value_uses_fallback_data_when_api_fails_and_data_is_six_days_old(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "dividend_yield", "2026-05-15", 2.1, "local"),
        ]
    )

    def fetch_missing():
        raise DataSourceError("source failed")

    result = service.query_value(
        asset_type="index",
        code="000300",
        metric="dividend_yield",
        requested_date="2026-05-21",
        fetch_missing=fetch_missing,
    )

    assert result.actual_date == "2026-05-15"
    assert result.value == 2.1
    assert result.stale is True


def test_query_value_rejects_fallback_data_when_api_fails_and_data_is_seven_days_old(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "dividend_yield", "2026-05-14", 2.1, "local"),
        ]
    )

    def fetch_missing():
        raise DataSourceError("source failed")

    try:
        service.query_value(
            asset_type="index",
            code="000300",
            metric="dividend_yield",
            requested_date="2026-05-21",
            fetch_missing=fetch_missing,
        )
    except ValueError as exc:
        message = str(exc)
        assert "Fallback data is too old" in message
        assert "requested_date=2026-05-21" in message
        assert "actual_date=2026-05-14" in message
        assert "max_age_days=7" in message
    else:
        raise AssertionError("Expected ValueError")


def test_query_rejects_fallback_data_when_api_fails_and_data_is_seven_days_old(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("gold", "AU9999", "close", "2026-05-14", 530.0, "local"),
        ]
    )

    def fetch_missing():
        raise DataSourceError("source failed")

    try:
        service.query(
            asset_type="gold",
            code="AU9999",
            metric="close",
            requested_date="2026-05-21",
            years=1,
            fetch_missing=fetch_missing,
        )
    except ValueError as exc:
        assert "Fallback data is too old" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


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


def test_query_erp_percentile_excludes_nonpositive_pe_rows(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)

    def fetch_erp():
        return compute_erp_rows(
            [
                DailyMetric("index", "000300", "rolling_pe", "2025-01-01", 0.0, "akshare"),
                DailyMetric("index", "000300", "rolling_pe", "2025-01-02", -10.0, "akshare"),
                DailyMetric("index", "000300", "rolling_pe", "2025-01-03", 50.0, "akshare"),
                DailyMetric("index", "000300", "rolling_pe", "2025-01-04", 25.0, "akshare"),
            ],
            [
                DailyMetric("bond", "CN10Y", "yield", "2025-01-01", 1.0, "akshare"),
                DailyMetric("bond", "CN10Y", "yield", "2025-01-02", 1.0, "akshare"),
                DailyMetric("bond", "CN10Y", "yield", "2025-01-03", 1.0, "akshare"),
                DailyMetric("bond", "CN10Y", "yield", "2025-01-04", 1.0, "akshare"),
            ],
        )

    result = service.query(
        asset_type="spread",
        code="000300",
        metric="erp",
        requested_date="2025-01-04",
        years=1,
        fetch_missing=fetch_erp,
    )

    assert result.sample_start_date == "2025-01-03"
    assert result.sample_count == 2
    assert result.value == 3.0
    assert result.percentile == 100.0


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


def test_query_range_rejects_fallback_data_when_api_fails_and_end_data_is_seven_days_old(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("gold", "AU9999", "close", "2026-05-14", 530.0, "local"),
        ]
    )

    def fetch_missing():
        raise DataSourceError("source failed")

    try:
        service.query_range(
            asset_type="gold",
            code="AU9999",
            metric="close",
            requested_from="2026-05-01",
            requested_to="2026-05-21",
            fetch_missing=fetch_missing,
        )
    except ValueError as exc:
        message = str(exc)
        assert "Fallback data is too old" in message
        assert "requested_date=2026-05-21" in message
        assert "actual_date=2026-05-14" in message
    else:
        raise AssertionError("Expected ValueError")


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
