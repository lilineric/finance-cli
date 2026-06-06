# Fund Info CLI Design

## Context

`finance-cli` currently has fund NAV support through `finance fund-nav`, but it does not
store or query non-NAV fund profile data. The existing architecture is:

- Typer commands in `src/finance_cli/cli.py`.
- Source adapters in `src/finance_cli/sources.py`.
- Query/write coordination in `src/finance_cli/service.py`.
- Remote SQLite API access in `src/finance_cli/db.py`.
- JSON and text formatting in `src/finance_cli/output.py`.

The current `daily_metrics` table is date-series oriented and is not a good fit for
fund profile snapshots. This feature adds a dedicated structured table for fund profile
data while preserving the existing remote SQLite API pattern.

There are pre-existing uncommitted changes in the working tree. This design only covers
the new fund info CLI and does not assume ownership of those changes.

## Goals

- Add a CLI to query fund profile data without fetching fund NAV.
- Store fund data in fixed structure fields, with normalized fee tiers stored as JSON arrays.
- Default query behavior reads the remote database first and avoids akshare when cached data exists.
- Support forced refresh from akshare that overwrites the stored fund profile.
- Support manual database updates from inline JSON or a JSON file.
- Keep the implementation small and aligned with the existing CLI, service, repository, and output layers.

## Non-Goals

- No fund NAV changes.
- No batch fund synchronization.
- No SQL-queryable fee tier tables.
- No fund screening or filtering command.
- No manager, custodian, minimum purchase amount, or maximum purchase amount fields.
- No storage of akshare raw payloads.
- No speculative fields beyond the agreed first-version schema.

## Commands

Add two top-level commands:

```bash
finance fund-info --code 017763
finance fund-info --code 017763 --refresh --json

finance fund-info-update --code 017763 --data '{"name":"银河领先债券C","purchase_fee":[],"redemption_fee":[],"source":"manual"}'
finance fund-info-update --code 017763 --data-file ./fund-info.json
```

`finance fund-info` queries one fund profile. `--refresh` forces a fresh akshare fetch,
upserts the result into the database, and returns the saved result.

`finance fund-info-update` manually upserts one fund profile. `--data` and `--data-file`
are mutually exclusive, and exactly one must be supplied. The JSON shape must match the
`fund-info --json` response shape.

Both commands support `--json`. Text output uses Chinese field labels and concise fee
tier summaries.

## Database Schema

Add a new table during repository initialization:

```sql
CREATE TABLE IF NOT EXISTS fund_info (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fund_type TEXT,
    established_date TEXT,
    asset_size TEXT,
    purchase_status TEXT,
    redemption_status TEXT,
    morningstar_rating TEXT,
    purchase_fee_json TEXT NOT NULL,
    redemption_fee_json TEXT NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

The table is separate from `daily_metrics` because fund profile data is a latest-known
snapshot, not a date series.

## Response Model

Use a dedicated data model, for example:

```python
@dataclass(frozen=True)
class FundInfo:
    code: str
    name: str
    fund_type: str | None
    established_date: str | None
    asset_size: str | None
    purchase_status: str | None
    redemption_status: str | None
    morningstar_rating: str | None
    purchase_fee: list[dict[str, object]]
    redemption_fee: list[dict[str, object]]
    source: str
    updated_at: str
```

JSON output:

```json
{
  "code": "017763",
  "name": "银河领先债券C",
  "fund_type": "债券型",
  "established_date": "2023-01-01",
  "asset_size": "10.25亿元",
  "purchase_status": "开放申购",
  "redemption_status": "开放赎回",
  "morningstar_rating": "5",
  "purchase_fee": [],
  "redemption_fee": [],
  "source": "akshare",
  "updated_at": "2026-06-07T12:00:00+00:00"
}
```

Fields with unknown values may be `null`, except `code`, `name`, `purchase_fee`,
`redemption_fee`, `source`, and `updated_at`.

## Fee Tier Format

`purchase_fee` is an array ordered by increasing purchase amount. Amounts are in CNY.
Rates use decimal values: `0.015` means `1.5%`.

```json
{
  "min_amount": 0,
  "max_amount": 1000000,
  "original_rate": 0.015,
  "discounted_rate": 0.0015
}
```

For tiers with no upper bound, `max_amount` is `null`.

For fixed-fee tiers, include `fixed_fee` and set rate fields to `null` if no rate applies:

```json
{
  "min_amount": 1000000,
  "max_amount": null,
  "original_rate": null,
  "discounted_rate": null,
  "fixed_fee": 1000
}
```

`redemption_fee` is an array ordered by increasing holding period. Holding periods are in
calendar days.

```json
{
  "min_holding_days": 0,
  "max_holding_days": 7,
  "original_rate": 0.015,
  "discounted_rate": 0.015
}
```

For tiers with no upper bound, `max_holding_days` is `null`.

Manual updates must use the same fee tier format. Unknown keys in fee tier objects are
invalid.

## Data Flow

`finance fund-info`:

1. Normalize `--code` to a 6-digit fund code.
2. Initialize the repository, including the new `fund_info` table.
3. If `--refresh` is absent, query `fund_info` by code.
4. If a row exists, return it without calling akshare.
5. If no row exists, or if `--refresh` is present, fetch from akshare.
6. Normalize and validate the fetched fund profile.
7. Upsert the profile into `fund_info`.
8. Return the saved profile.

`finance fund-info-update`:

1. Normalize `--code`.
2. Read JSON from `--data` or `--data-file`.
3. Validate that the top-level shape matches the response model.
4. If JSON includes `code`, it must match `--code`.
5. Reject unknown top-level fields.
6. Validate the fee tier arrays and value types.
7. Upsert the profile into `fund_info`.
8. Return the saved profile.

## akshare Mapping

Add a source function such as `fetch_fund_info(code)`.

The source function aggregates:

- `fund_individual_basic_info_xq(code)` for core profile fields such as `name`,
  `fund_type`, `established_date`, and `asset_size`.
- `fund_purchase_em()` for `purchase_status` and, when available, `redemption_status`.
- `fund_fee_em(code, indicator="申购费率（前端）")` for `purchase_fee`.
- `fund_fee_em(code, indicator="赎回费率")` for `redemption_fee`.
- `fund_rating_all()` for `morningstar_rating`.

The implementation should inspect the returned DataFrame columns and normalize from the
actual akshare column names used by the installed version. Tests should cover normalization
using representative DataFrames rather than relying on live network calls.

## Error Handling

Use existing CLI error behavior:

- Validation errors return `invalid_parameter`.
- SQLite API failures return `sqlite_api_error`.
- akshare/source failures return `runtime_error`.

Specific rules:

- Invalid fund codes are rejected before database or akshare work.
- `--data` and `--data-file` conflict is `invalid_parameter`.
- Missing both `--data` and `--data-file` is `invalid_parameter`.
- Invalid JSON is `invalid_parameter`.
- Unknown top-level fields are `invalid_parameter`.
- JSON `code` mismatch with `--code` is `invalid_parameter`.
- Fee tier objects with unknown fields or wrong value types are `invalid_parameter`.
- If the core basic-info source fails, fetched fund info fails and must not overwrite old data.
- If fee, purchase-status, redemption-status, or rating data is unavailable, fetched fund info
  can still be saved with `null` fields or empty fee arrays.
- If a fee row cannot be parsed into the normalized tier format, fetched fund info fails and
  must not overwrite old data.
- If default `fund-info` fetch fails but the database has cached data, return the cached data.
- If `fund-info --refresh` fetch fails, return an error and leave existing database data unchanged.

## Testing

Add focused tests for:

- Repository initialization creates `fund_info`.
- Repository upsert/query maps `FundInfo` to and from SQLite API payloads.
- `fund-info` returns cached data without calling akshare.
- `fund-info` fetches, stores, and returns data when cache is missing.
- `fund-info --refresh` fetches and overwrites even when cache exists.
- `fund-info-update --data` writes a valid payload.
- `fund-info-update --data-file` writes a valid payload.
- CLI rejects missing/conflicting update inputs.
- CLI rejects invalid JSON, unknown fields, mismatched code, and invalid fee tier shapes.
- Source normalization parses purchase fee tiers by amount.
- Source normalization parses redemption fee tiers by holding period.
- Source normalization handles no upper bound, fixed fees, original rates, and discounted rates.
- Source aggregation tolerates missing non-core optional data.
- README documents the new commands and JSON format.

## Implementation Notes

- Add a dedicated repository API for fund info instead of reusing `DailyMetric`.
- Add service methods for cached query, forced refresh, and manual upsert.
- Add separate output formatters for fund info JSON and text.
- Keep changes surgical and avoid a broad metric registry refactor.
- Do not modify existing `fund-nav` behavior.
