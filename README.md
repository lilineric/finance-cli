# finance-cli

Financial data CLI backed by SQLite and akshare.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Commands

Query index PE-TTM percentile:

```bash
finance pe --code 000300 --date 2026-04-20 --years 10
```

Query Shanghai Gold Exchange Au9999 close-price percentile:

```bash
finance gold --date 2026-04-20 --years 10
```

Output JSON:

```bash
finance pe --code 000300 --date 2026-04-20 --json
```

Manually synchronize data:

```bash
finance sync pe --code 000300
finance sync gold
```

Query commands auto-refresh local data when needed.
Percentiles use available local or source samples within the requested lookback window; output includes sample count and sample start date to show actual coverage.

## Database

By default, data is stored at:

```text
~/.finance-cli/finance.db
```

Override the path with:

```bash
FINANCE_CLI_DB=/path/to/finance.db finance gold
```
