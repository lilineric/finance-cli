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

Query index dividend-yield percentile:

```bash
finance dividend-yield --code 000300 --date 2026-04-20 --years 10
```

Query SW index PB percentile:

```bash
finance pb --code 801010 --category 一级行业 --date 2026-04-20 --years 10
```

Query Shanghai Gold Exchange Au9999 close-price percentile:

```bash
finance gold --date 2026-04-20 --years 10
```

Query China 10-year government bond yield percentile:

```bash
finance cn10y-yield --date 2026-04-20 --years 10
```

Output JSON:

```bash
finance pe --code 000300 --date 2026-04-20 --json
```

Manually synchronize data:

```bash
finance sync pe --code 000300
finance sync dividend-yield --code 000300
finance sync pb --code 801010 --category 一级行业
finance sync gold
finance sync cn10y-yield
```

Query commands auto-refresh local data when needed.
Percentiles use available local or source samples within the requested lookback window; output includes sample count and sample start date to show actual coverage.
PB uses the SW index analysis source and requires `--category`: `市场表征`, `一级行业`, `二级行业`, or `风格指数`.

## Database

By default, data is stored at:

```text
~/.finance-cli/finance.db
```

Override the path with:

```bash
FINANCE_CLI_DB=/path/to/finance.db finance gold
```
