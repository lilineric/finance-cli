from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date

from finance_cli.analytics import (
    calculate_percentile,
    parse_query_date,
    start_date_for_years,
    validate_years,
)
from finance_cli.db import DailyMetric, FundInfo, MetricsRepository
from finance_cli.sources import DataSourceError


LOOKBACK_COVERAGE_GRACE_DAYS = 7
STALE_FALLBACK_MAX_AGE_DAYS = 7
DAYS_PER_YEAR = 365.2425


@dataclass(frozen=True)
class MetricQueryResult:
    asset_type: str
    code: str
    metric: str
    requested_date: str
    actual_date: str
    sample_start_date: str | None
    value: float
    percentile: float | None
    sample_count: int | None
    source: str
    lookback_years: int | None
    coverage_status: str | None = None
    effective_years: float | None = None
    stale: bool = False


@dataclass(frozen=True)
class MetricRangeQueryResult:
    asset_type: str
    code: str
    metric: str
    requested_from: str
    requested_to: str
    actual_start_date: str
    actual_end_date: str
    data: list[tuple[str, float, str]]
    stale: bool = False


@dataclass(frozen=True)
class MoneyFundQueryResult:
    asset_type: str
    code: str
    fund_type: str
    requested_date: str
    actual_date: str
    metrics: dict[str, float]
    source: str
    stale: bool = False


@dataclass(frozen=True)
class MoneyFundRangeQueryResult:
    asset_type: str
    code: str
    fund_type: str
    requested_from: str
    requested_to: str
    actual_start_date: str
    actual_end_date: str
    data: list[tuple[str, dict[str, float], str]]
    stale: bool = False


@dataclass(frozen=True)
class FundInfoChange:
    field: str
    label: str
    old: object
    new: object


@dataclass(frozen=True)
class FundInfoSyncSuccess:
    code: str
    name: str
    changes: list[FundInfoChange]


@dataclass(frozen=True)
class FundInfoSyncFailure:
    code: str
    error: str


@dataclass(frozen=True)
class FundInfoSyncResult:
    total: int
    successes: list[FundInfoSyncSuccess]
    failures: list[FundInfoSyncFailure]

    @property
    def updated(self) -> int:
        return len(self.successes)

    @property
    def unchanged(self) -> int:
        return len([success for success in self.successes if not success.changes])

    @property
    def failed(self) -> int:
        return len(self.failures)


class MetricsService:
    def __init__(self, repository: MetricsRepository) -> None:
        self.repository = repository

    def sync(self, fetch_rows: Callable[[], Iterable[DailyMetric]]) -> int:
        self.repository.initialize()
        rows = list(fetch_rows())
        return self.repository.upsert_metrics(rows)

    def replace_sync(
        self,
        asset_type: str,
        code: str,
        metric: str,
        fetch_rows: Callable[[], Iterable[DailyMetric]],
    ) -> int:
        self.repository.initialize()
        rows = list(fetch_rows())
        self.repository.delete_metrics(asset_type, code, metric)
        return self.repository.upsert_metrics(rows)

    def query_fund_info(
        self,
        code: str,
        fetch_missing: Callable[[], FundInfo],
        refresh: bool = False,
    ) -> FundInfo:
        self.repository.initialize()
        cached = None if refresh else self.repository.fund_info_by_code(code)
        if cached is not None:
            return cached

        try:
            fresh = fetch_missing()
        except DataSourceError:
            if refresh:
                raise
            fallback = self.repository.fund_info_by_code(code)
            if fallback is None:
                raise
            return fallback

        self.repository.upsert_fund_info(fresh)
        return fresh

    def update_fund_info(self, fund_info: FundInfo) -> FundInfo:
        self.repository.initialize()
        self.repository.upsert_fund_info(fund_info)
        return fund_info

    def sync_fund_info(
        self,
        fetch_fund_info: Callable[[str], FundInfo],
        max_workers: int = 5,
    ) -> FundInfoSyncResult:
        self.repository.initialize()
        codes = self.repository.fund_info_codes()
        cached_by_code = {code: self.repository.fund_info_by_code(code) for code in codes}
        if not codes:
            return FundInfoSyncResult(total=0, successes=[], failures=[])

        fetched_by_code: dict[str, FundInfo] = {}
        failures: list[FundInfoSyncFailure] = []
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            futures = {executor.submit(fetch_fund_info, code): code for code in codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    fetched_by_code[code] = future.result()
                except Exception as exc:
                    failures.append(FundInfoSyncFailure(code=code, error=str(exc)))

        successes: list[FundInfoSyncSuccess] = []
        for code in codes:
            fresh = fetched_by_code.get(code)
            if fresh is None:
                continue
            try:
                self.repository.upsert_fund_info(fresh)
            except Exception as exc:
                failures.append(FundInfoSyncFailure(code=code, error=str(exc)))
                continue
            successes.append(
                FundInfoSyncSuccess(
                    code=fresh.code,
                    name=fresh.name,
                    changes=_fund_info_changes(cached_by_code.get(code), fresh),
                )
            )

        return FundInfoSyncResult(total=len(codes), successes=successes, failures=failures)

    def query(
        self,
        asset_type: str,
        code: str,
        metric: str,
        requested_date: str,
        years: int,
        fetch_missing: Callable[[], Iterable[DailyMetric]],
        ensure_lookback_coverage: bool = False,
        minimum_lookback_years: int | None = None,
    ) -> MetricQueryResult:
        parsed_requested_date = parse_query_date(requested_date)
        validated_years = validate_years(years)
        requested_date_text = parsed_requested_date.isoformat()

        self.repository.initialize()
        actual_date = self.repository.latest_date_on_or_before(
            asset_type,
            code,
            metric,
            requested_date_text,
        )
        stale = False
        if actual_date is None or not self._has_local_data_on_or_after(
            asset_type,
            code,
            metric,
            requested_date_text,
        ):
            try:
                self.repository.upsert_metrics(list(fetch_missing()))
                actual_date = self.repository.latest_date_on_or_before(
                    asset_type,
                    code,
                    metric,
                    requested_date_text,
                )
            except DataSourceError:
                if actual_date is None:
                    raise
                stale = True

        if actual_date is None:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} on or before {requested_date_text}"
            )
        if stale:
            _raise_if_stale_fallback_too_old(
                asset_type,
                code,
                metric,
                requested_date_text,
                actual_date,
            )

        parsed_actual_date = parse_query_date(actual_date)
        start_date = start_date_for_years(parsed_actual_date, validated_years).isoformat()
        rows = self.repository.metrics_between(
            asset_type,
            code,
            metric,
            start_date,
            actual_date,
        )
        if ensure_lookback_coverage and rows and _has_incomplete_lookback(rows[0].date, start_date):
            try:
                self.repository.upsert_metrics(list(fetch_missing()))
                actual_date = self.repository.latest_date_on_or_before(
                    asset_type,
                    code,
                    metric,
                    requested_date_text,
                )
            except DataSourceError:
                stale = True
            if actual_date is None and not stale:
                raise ValueError(
                    f"No data available for {asset_type} {code} {metric} on or before {requested_date_text}"
                )
            parsed_actual_date = parse_query_date(actual_date)
            start_date = start_date_for_years(parsed_actual_date, validated_years).isoformat()
            rows = self.repository.metrics_between(
                asset_type,
                code,
                metric,
                start_date,
                actual_date,
            )
            if stale:
                _raise_if_stale_fallback_too_old(
                    asset_type,
                    code,
                    metric,
                    requested_date_text,
                    actual_date,
                )
        if not rows:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} between {start_date} and {actual_date}"
            )
        has_incomplete_lookback = _has_incomplete_lookback(rows[0].date, start_date)
        coverage_status = None
        effective_years = None
        if ensure_lookback_coverage and has_incomplete_lookback:
            minimum_start_date = _minimum_start_date(parsed_actual_date, minimum_lookback_years)
            if not stale and (
                minimum_start_date is None or _has_incomplete_lookback(rows[0].date, minimum_start_date)
            ):
                minimum_text = "" if minimum_start_date is None else f"minimum_start_date={minimum_start_date}, "
                raise ValueError(
                    "Sample coverage is incomplete: "
                    f"asset_type={asset_type}, code={code}, metric={metric}, "
                    f"lookback_years={validated_years}, expected_start_date={start_date}, "
                    f"{minimum_text}sample_start_date={rows[0].date}, sample_count={len(rows)}"
                )
            coverage_status = "partial"
            effective_years = _effective_years(rows[0].date, actual_date)

        current_row = rows[-1]
        return MetricQueryResult(
            asset_type=asset_type,
            code=code,
            metric=metric,
            requested_date=requested_date_text,
            actual_date=current_row.date,
            sample_start_date=rows[0].date,
            value=current_row.value,
            percentile=calculate_percentile((row.value for row in rows), current_row.value),
            sample_count=len(rows),
            source=current_row.source,
            lookback_years=validated_years,
            coverage_status=coverage_status,
            effective_years=effective_years,
            stale=stale,
        )

    def query_value(
        self,
        asset_type: str,
        code: str,
        metric: str,
        requested_date: str,
        fetch_missing: Callable[[], Iterable[DailyMetric]],
        refresh_stale: bool = True,
    ) -> MetricQueryResult:
        parsed_requested_date = parse_query_date(requested_date)
        requested_date_text = parsed_requested_date.isoformat()

        self.repository.initialize()
        actual_date = self.repository.latest_date_on_or_before(
            asset_type,
            code,
            metric,
            requested_date_text,
        )
        stale = False
        if actual_date is None or (
            refresh_stale
            and not self._has_local_data_on_or_after(
                asset_type,
                code,
                metric,
                requested_date_text,
            )
        ):
            try:
                self.repository.upsert_metrics(list(fetch_missing()))
                actual_date = self.repository.latest_date_on_or_before(
                    asset_type,
                    code,
                    metric,
                    requested_date_text,
                )
            except DataSourceError:
                if actual_date is None:
                    raise
                stale = True

        if actual_date is None:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} on or before {requested_date_text}"
            )
        if stale:
            _raise_if_stale_fallback_too_old(
                asset_type,
                code,
                metric,
                requested_date_text,
                actual_date,
            )

        rows = self.repository.metrics_between(
            asset_type,
            code,
            metric,
            actual_date,
            actual_date,
        )
        if not rows:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} on {actual_date}"
            )

        current_row = rows[-1]
        return MetricQueryResult(
            asset_type=asset_type,
            code=code,
            metric=metric,
            requested_date=requested_date_text,
            actual_date=current_row.date,
            sample_start_date=None,
            value=current_row.value,
            percentile=None,
            sample_count=None,
            source=current_row.source,
            lookback_years=None,
            stale=stale,
        )

    def query_range(
        self,
        asset_type: str,
        code: str,
        metric: str,
        requested_from: str,
        requested_to: str,
        fetch_missing: Callable[[], Iterable[DailyMetric]],
    ) -> MetricRangeQueryResult:
        parsed_from = parse_query_date(requested_from)
        parsed_to = parse_query_date(requested_to)
        if parsed_from > parsed_to:
            raise ValueError("from date must be on or before to date")

        from_text = parsed_from.isoformat()
        to_text = parsed_to.isoformat()

        self.repository.initialize()
        rows = self.repository.metrics_between(
            asset_type,
            code,
            metric,
            from_text,
            to_text,
        )
        stale = False
        if not self._has_local_data_on_or_after(
            asset_type,
            code,
            metric,
            to_text,
        ):
            try:
                self.repository.upsert_metrics(list(fetch_missing()))
                rows = self.repository.metrics_between(
                    asset_type,
                    code,
                    metric,
                    from_text,
                    to_text,
                )
            except DataSourceError:
                if not rows:
                    raise
                stale = True

        if not rows:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} between {from_text} and {to_text}"
            )
        if stale:
            _raise_if_stale_fallback_too_old(
                asset_type,
                code,
                metric,
                to_text,
                rows[-1].date,
            )

        return MetricRangeQueryResult(
            asset_type=asset_type,
            code=code,
            metric=metric,
            requested_from=from_text,
            requested_to=to_text,
            actual_start_date=rows[0].date,
            actual_end_date=rows[-1].date,
            data=[(row.date, row.value, row.source) for row in rows],
            stale=stale,
        )

    def _has_local_data_on_or_after(
        self,
        asset_type: str,
        code: str,
        metric: str,
        requested_date: str,
    ) -> bool:
        return bool(
            self.repository.metrics_between(
                asset_type,
                code,
                metric,
                requested_date,
                "9999-12-31",
            )
        )


def _fund_info_changes(old: FundInfo | None, new: FundInfo) -> list[FundInfoChange]:
    if old is None:
        return []

    checks = [
        ("purchase_status", "申购状态", old.purchase_status, new.purchase_status),
        ("purchase_limit_amount", "限购金额", old.purchase_limit_amount, new.purchase_limit_amount),
        ("redemption_status", "赎回状态", old.redemption_status, new.redemption_status),
        (
            "operation_fee.management_fee",
            "管理费率",
            old.operation_fee.management_fee,
            new.operation_fee.management_fee,
        ),
        (
            "operation_fee.custodian_fee",
            "托管费率",
            old.operation_fee.custodian_fee,
            new.operation_fee.custodian_fee,
        ),
        (
            "operation_fee.sales_service_fee",
            "销售服务费率",
            old.operation_fee.sales_service_fee,
            new.operation_fee.sales_service_fee,
        ),
        ("purchase_fee", "申购费率", old.purchase_fee, new.purchase_fee),
        ("redemption_fee", "赎回费率", old.redemption_fee, new.redemption_fee),
    ]
    return [
        FundInfoChange(field=field, label=label, old=old_value, new=new_value)
        for field, label, old_value, new_value in checks
        if old_value != new_value
    ]


def _has_incomplete_lookback(sample_start_date: str, expected_start_date: str) -> bool:
    sample_start = parse_query_date(sample_start_date)
    expected_start = parse_query_date(expected_start_date)
    return (sample_start - expected_start).days > LOOKBACK_COVERAGE_GRACE_DAYS


def _raise_if_stale_fallback_too_old(
    asset_type: str,
    code: str,
    metric: str,
    requested_date: str,
    actual_date: str,
) -> None:
    requested = parse_query_date(requested_date)
    actual = parse_query_date(actual_date)
    if (requested - actual).days >= STALE_FALLBACK_MAX_AGE_DAYS:
        raise ValueError(
            "Fallback data is too old: "
            f"asset_type={asset_type}, code={code}, metric={metric}, "
            f"requested_date={requested_date}, actual_date={actual_date}, "
            f"max_age_days={STALE_FALLBACK_MAX_AGE_DAYS}"
        )


def _minimum_start_date(actual_date: date, minimum_lookback_years: int | None) -> str | None:
    if minimum_lookback_years is None:
        return None
    return start_date_for_years(actual_date, minimum_lookback_years).isoformat()


def _effective_years(sample_start_date: str, actual_date: str) -> float:
    sample_start = parse_query_date(sample_start_date)
    actual = parse_query_date(actual_date)
    return round((actual - sample_start).days / DAYS_PER_YEAR, 1)
