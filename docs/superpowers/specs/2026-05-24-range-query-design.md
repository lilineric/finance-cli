# Finance CLI Range Query Design

## Context

`finance-cli` currently supports single-date queries for these metrics:

- `finance pe`: index `rolling_pe`, with percentile output.
- `finance dividend-yield`: index `dividend_yield`, value-only output.
- `finance pb`: index or SW index `pb`, value-only output.
- `finance gold`: Au9999 `close`, with percentile output.
- `finance cn10y-yield`: China 10-year government bond `yield`, with percentile output.
- `finance fund-nav`: fund `unit_nav` or `accumulated_nav`, value-only output.

Single-date percentile commands use `MetricsService.query(...)`. Value-only commands use
`MetricsService.query_value(...)`. The repository already provides `metrics_between(...)`,
which is the right storage primitive for date-range retrieval.

There are existing uncommitted code changes in the working tree. This design only describes
the new feature and does not assume ownership of those changes.

## Goals

- Add date-range query capability to every existing query command.
- Use `--from` and `--to` to request all available metric values in the inclusive date range.
- Return JSON with query metadata, actual data coverage dates, and raw value rows.
- Never include percentile-related fields in range results.
- Preserve existing single-date command behavior when `--from/--to` are not provided.
- Keep the implementation small and aligned with the current service/output/CLI structure.

## Non-Goals

- No new top-level `range` or `metrics` command.
- No percentile calculation for range results.
- No forward-fill, calendar filling, interpolation, or synthetic rows.
- No new database schema.
- No broad metric registry refactor.
- No unrelated cleanup of existing CLI, source, or service code.

## Command Shape

Each existing query command gains `--from` and `--to` options:

```bash
finance pe --code 000300 --from 2026-01-01 --to 2026-05-01 --json
finance dividend-yield --code 000300 --from 2026-01-01 --to 2026-05-01 --json
finance pb --code 930707 --from 2026-01-01 --to 2026-05-01 --json
finance pb --code 801010 --category 一级行业 --from 2026-01-01 --to 2026-05-01 --json
finance gold --from 2026-01-01 --to 2026-05-01 --json
finance cn10y-yield --from 2026-01-01 --to 2026-05-01 --json
finance fund-nav --code 017763 --nav-type unit --from 2026-01-01 --to 2026-05-01 --json
finance fund-nav --code 017763 --nav-type accumulated --from 2026-01-01 --to 2026-05-01 --json
```

`--from` and `--to` are inclusive. They must be supplied together.

## Parameter Rules

Range mode starts when either `--from` or `--to` is present.

Validation rules:

- `--from` and `--to` must be supplied together.
- Dates must use `YYYY-MM-DD`.
- `--from` must be less than or equal to `--to`.
- Range mode cannot be combined with an explicitly supplied `--date`.
- Range mode cannot be combined with an explicitly supplied `--years` on `pe`, `gold`, or `cn10y-yield`.

The existing `--code`, `--category`, and `--nav-type` validations continue to apply.

Existing single-date defaults must keep working. The implementation should avoid treating the
implicit default `--date=today` or `--years=10` as user-supplied range-mode conflicts. A simple
way to do this is to make command parameters optional internally, detect whether the user supplied
range options, and apply the single-date defaults only in the single-date branch.

## Service Design

Add a range result model:

```python
@dataclass(frozen=True)
class MetricRangeValue:
    date: str
    value: float
    source: str


@dataclass(frozen=True)
class MetricRangeQueryResult:
    asset_type: str
    code: str
    metric: str
    requested_from: str
    requested_to: str
    actual_start_date: str
    actual_end_date: str
    data: list[MetricRangeValue]
```

Add `MetricsService.query_range(...)`:

```python
def query_range(
    self,
    asset_type: str,
    code: str,
    metric: str,
    requested_from: str,
    requested_to: str,
    fetch_missing: Callable[[], Iterable[DailyMetric]],
) -> MetricRangeQueryResult:
    ...
```

Behavior:

1. Parse and validate `requested_from` and `requested_to`.
2. Initialize the repository.
3. Query `repository.metrics_between(asset_type, code, metric, from, to)`.
4. If there is no local data on or after `requested_to`, call `fetch_missing`, upsert rows, and query again.
5. If the final range query returns no rows, raise a clear no-data `ValueError`.
6. Return rows sorted by date, using the repository ordering.

This follows the existing refresh pattern: local data is considered stale for a requested range
when the repository has no data on or after the requested end date.

## CLI Mapping

The existing commands keep their metric mappings:

- `pe`: `asset_type="index"`, normalized code, `metric="rolling_pe"`, fetch with `fetch_index_pe_rows`.
- `dividend-yield`: `asset_type="index"`, normalized code, `metric="dividend_yield"`, fetch with `fetch_index_dividend_yield_rows`.
- `pb` without `--category`: `asset_type="index"`, raw CSI PB code normalized by `fetch_index_pb_rows`, `metric="pb"`.
- `pb` with `--category`: `asset_type=f"sw_index:{category}"`, code as supplied, `metric="pb"`, fetch with `fetch_sw_index_pb_rows`.
- `gold`: `asset_type="gold"`, `code="AU9999"`, `metric="close"`, fetch with `fetch_gold_rows`.
- `cn10y-yield`: `asset_type="bond"`, `code="CN10Y"`, `metric="yield"`, fetch with `fetch_cn10y_yield_rows`.
- `fund-nav`: `asset_type="fund"`, normalized fund code, `metric="unit_nav"` or `metric="accumulated_nav"`, fetch with `fetch_fund_nav_rows`.

CLI functions should branch early:

- If range options are absent, use the existing single-date code path.
- If range options are present, validate range-only parameter rules and call `query_range`.

## JSON Output

Add `format_range_json(result: MetricRangeQueryResult) -> str`.

Example output:

```json
{
  "asset_type": "index",
  "code": "000300",
  "metric": "rolling_pe",
  "requested_from": "2026-01-01",
  "requested_to": "2026-05-01",
  "actual_start_date": "2026-01-02",
  "actual_end_date": "2026-04-30",
  "data": [
    {"date": "2026-01-02", "value": 12.3, "source": "akshare"},
    {"date": "2026-01-05", "value": 12.5, "source": "akshare"}
  ]
}
```

Range JSON must not include these keys:

- `percentile`
- `sample_count`
- `sample_start_date`
- `lookback_years`
- `coverage_status`
- `effective_years`

`actual_start_date` is the first returned row date. `actual_end_date` is the last returned row date.

## Text Output

JSON is the primary machine interface for range queries. Text output can stay simple and stable:

```text
指数: 000300
请求起始日期: 2026-01-01
请求结束日期: 2026-05-01
实际起始日期: 2026-01-02
实际结束日期: 2026-04-30
指标: rolling_pe
2026-01-02 12.3 akshare
2026-01-05 12.5 akshare
```

Text range output also must not mention percentiles, lookback years, sample counts, or sample
start dates.

## Error Handling

Use the existing JSON error wrapper when `--json` is present:

```json
{"error": {"code": "invalid_parameter", "message": "..."}}
```

New invalid-parameter cases:

- Missing `--from` or missing `--to`.
- `--from > --to`.
- Range mode combined with `--date`.
- Range mode combined with `--years`.

Existing data source and SQLite API errors keep their current classification. A refreshed range
with no rows should raise a no-data `ValueError`, which the current CLI error path treats as a
runtime error.

## Testing Strategy

Service tests:

- `query_range` returns only rows within `[from, to]`, sorted by date.
- `query_range` sets `actual_start_date` and `actual_end_date` from returned rows.
- `query_range` does not calculate or expose percentile fields.
- `query_range` does not fetch when local data exists on or after `requested_to`.
- `query_range` fetches when local data is stale for the requested end date.
- `query_range` raises when refreshed data still has no rows in the requested range.
- `query_range` rejects `from > to`.

Output tests:

- `format_range_json` emits stable top-level keys.
- `format_range_json` emits `data` rows with only `date`, `value`, and `source`.
- `format_range_json` omits all percentile-related keys.
- Range text output omits percentile-related labels.

CLI tests:

- `pe --from --to --json` calls `query_range` with `rolling_pe`.
- `dividend-yield --from --to --json` calls `query_range` with `dividend_yield`.
- `pb --from --to --json` works without `--category` for CSI PB.
- `pb --category ... --from --to --json` works for SW PB.
- `gold --from --to --json` calls `query_range` with `close`.
- `cn10y-yield --from --to --json` calls `query_range` with `yield`.
- `fund-nav --nav-type unit --from --to --json` calls `query_range` with `unit_nav`.
- `fund-nav --nav-type accumulated --from --to --json` calls `query_range` with `accumulated_nav`.
- Missing `--to`, mixed `--date`, mixed `--years`, invalid dates, and `from > to` fail with clear errors.

## Assumptions

- The feature should cover every existing query command, not `sync` commands.
- Returning only actual source rows is correct; no date filling is desired.
- `--json` is the main expected consumption path for range queries.
- The current SQLite schema and `metrics_between` method are sufficient.
- Keeping range behavior inside existing command names is preferred over adding a new command layer.
