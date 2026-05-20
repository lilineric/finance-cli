from collections.abc import Callable, Iterable
from dataclasses import dataclass

from finance_cli.analytics import (
    calculate_percentile,
    parse_query_date,
    start_date_for_years,
    validate_years,
)
from finance_cli.db import DailyMetric, MetricsRepository


@dataclass(frozen=True)
class MetricQueryResult:
    asset_type: str
    code: str
    metric: str
    requested_date: str
    actual_date: str
    value: float
    percentile: float
    sample_count: int
    source: str


class MetricsService:
    def __init__(self, repository: MetricsRepository) -> None:
        self.repository = repository

    def sync(self, fetch_rows: Callable[[], Iterable[DailyMetric]]) -> int:
        self.repository.initialize()
        rows = list(fetch_rows())
        return self.repository.upsert_metrics(rows)

    def query(
        self,
        asset_type: str,
        code: str,
        metric: str,
        requested_date: str,
        years: int,
        fetch_missing: Callable[[], Iterable[DailyMetric]],
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
        if actual_date is None or not self._has_local_data_on_or_after(
            asset_type,
            code,
            metric,
            requested_date_text,
        ):
            self.repository.upsert_metrics(list(fetch_missing()))
            actual_date = self.repository.latest_date_on_or_before(
                asset_type,
                code,
                metric,
                requested_date_text,
            )

        if actual_date is None:
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
        if not rows:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} between {start_date} and {actual_date}"
            )

        current_row = rows[-1]
        return MetricQueryResult(
            asset_type=asset_type,
            code=code,
            metric=metric,
            requested_date=requested_date_text,
            actual_date=current_row.date,
            value=current_row.value,
            percentile=calculate_percentile((row.value for row in rows), current_row.value),
            sample_count=len(rows),
            source=current_row.source,
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
