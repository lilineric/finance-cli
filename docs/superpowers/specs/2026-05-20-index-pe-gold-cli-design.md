# Index PE and Gold Percentile CLI Design

## Context

`finance-cli` is currently a minimal repository with only a README. This feature will establish the first Python CLI structure and add two data-backed commands:

- `finance pe`: query an index PE-TTM value and its historical percentile.
- `finance gold`: query Shanghai Gold Exchange Au9999 close price and its historical percentile.

The same data pipeline will also support manual sync commands.

## Goals

- Provide one main CLI command, `finance`, with PE and gold subcommands.
- Store historical daily metrics in SQLite.
- Fetch source data with akshare.
- For a user-specified date, use the latest available data date that is less than or equal to that date.
- Compute percentiles from historical data ending at the actual data date, without using future data.
- Default to a 10-year lookback window and allow shorter windows up to a maximum of 10 years.
- Output human-readable text by default and JSON when `--json` is passed.

## Non-Goals

- No UI or web service.
- No portfolio-level analysis in this feature.
- No separate trading calendar table in the initial implementation.
- No support for non-Au9999 gold series in the initial implementation.
- No complex validation of index code formats beyond handling empty source results.

## Command Shape

Query commands:

```bash
finance pe --code 000300 --date 2026-04-20 --years 10
finance gold --date 2026-04-20 --years 10
```

Sync commands:

```bash
finance sync pe --code 000300
finance sync gold
```

Common query options:

- `--date`: optional `YYYY-MM-DD`, defaults to the current date.
- `--years`: optional integer, defaults to `10`, must be `1` through `10`.
- `--json`: optional flag for machine-readable JSON output.

PE-specific options:

- `--code`: required index code, such as `000300`.

Gold-specific behavior:

- Uses fixed code `AU9999`.
- Uses the Shanghai Gold Exchange Au9999 close price.

## Data Model

Use one generic daily metrics table so future metrics can be added without schema changes.

```sql
CREATE TABLE IF NOT EXISTS daily_metrics (
  asset_type TEXT NOT NULL,
  code TEXT NOT NULL,
  metric TEXT NOT NULL,
  date TEXT NOT NULL,
  value REAL NOT NULL,
  source TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (asset_type, code, metric, date)
);
```

SQLite does not have a true date storage type. Dates will be stored as ISO-8601 text (`YYYY-MM-DD`), which preserves chronological ordering for equality and range queries.

Metric mappings:

- Index PE-TTM: `asset_type = 'index'`, `code = user code`, `metric = 'pe_ttm'`.
- Gold Au9999 close: `asset_type = 'gold'`, `code = 'AU9999'`, `metric = 'close'`.

Primary access pattern:

```sql
WHERE asset_type = ?
  AND code = ?
  AND metric = ?
  AND date >= ?
  AND date <= ?
ORDER BY date
```

The primary key covers this query shape. No extra index is needed initially.

## Database Location

Default database path:

```text
~/.finance-cli/finance.db
```

The path can be overridden with:

```text
FINANCE_CLI_DB=/path/to/finance.db
```

Tests will use temporary SQLite database files.

## Data Sync

Both query commands and `sync` commands use the same data source layer.

Query behavior:

1. Determine requested date and lookback window.
2. Check whether SQLite has usable data for the requested asset and metric.
3. If needed, fetch historical data from akshare and upsert it into SQLite.
4. Re-query SQLite for calculation.

Manual sync behavior:

- `finance sync pe --code 000300` fetches and stores available PE-TTM history for that index.
- `finance sync gold` fetches and stores available Au9999 close price history.

If akshare returns insufficient history, the CLI still computes a percentile with available samples and displays the sample count. If no usable data exists on or before the requested date, the command fails.

## Percentile Calculation

For both PE and gold:

1. Parse `--date`, defaulting to the current date.
2. Find the latest stored date `<= requested_date` for the selected asset and metric.
3. Treat that date as `actual_date`.
4. Query values in `[actual_date - years, actual_date]`.
5. Compute percentile using only values with `date <= actual_date`.

Percentile formula:

```text
count(values <= current_value) / count(values) * 100
```

This makes a historical maximum return `100%`. A historical minimum returns `1 / sample_count * 100`, not `0%`.

## Output

Human-readable PE output should include:

- Index code.
- Requested date.
- Actual data date.
- Metric name and source.
- PE-TTM value.
- Lookback years.
- Historical percentile.
- Sample count.

Human-readable gold output should include:

- Symbol `AU9999`.
- Requested date.
- Actual data date.
- Metric name and source.
- Close price.
- Lookback years.
- Historical percentile.
- Sample count.

`--json` output should include equivalent fields with stable keys.

## Error Handling

- `--years > 10`: fail with a clear validation error.
- `--years <= 0`: fail with a clear validation error.
- Invalid `--date` format: fail with a clear validation error.
- akshare fetch failure: fail with a data source error and include a short exception summary.
- Empty akshare result: fail with a clear no-data message.
- No stored data on or before requested date after sync: fail with a clear no-data message.

## Testing Strategy

Unit tests:

- Percentile calculation with normal data.
- Non-trading requested date falls back to the nearest earlier available data date.
- Future rows in the database are excluded from the calculation.
- `--years` validation rejects values outside `1..10`.

Database tests:

- Schema creation.
- Upsert behavior.
- Latest date lookup.
- Range query for a lookback window.

Source tests:

- Mock akshare responses.
- Verify raw source frames are converted into `daily_metrics` rows.
- Avoid real network calls in unit tests.

CLI tests:

- `finance pe` text output.
- `finance gold` text output.
- `--json` output shape.
- Error output for invalid parameters and no-data cases.

## Assumptions

- The initial implementation will use Python.
- Typer is an acceptable CLI framework unless implementation discovery finds a simpler project-local convention.
- akshare has usable interfaces for index PE-TTM and Shanghai Gold Exchange Au9999 historical prices; exact adapter function names will be confirmed during implementation.
- Storing dates as `YYYY-MM-DD` text is the correct SQLite representation for this project.
