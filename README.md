# finance-cli

Financial data CLI backed by SQLite and akshare.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Commands

Query index rolling PE percentile:

```bash
finance pe --code 000300 --date 2026-04-20 --years 10
```

Rolling PE uses the CSIndex historical `滚动市盈率` field and is stored as `rolling_pe`.

Query index dividend-yield value:

```bash
finance dividend-yield --code 000300 --date 2026-04-20
```

Index dividend-yield returns the current value only; it does not calculate a historical percentile.

Query SW index PB value:

```bash
finance pb --code 801010 --category 一级行业 --date 2026-04-20
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
Percentiles use samples within the requested lookback window; output includes sample count and sample start date to show actual coverage.
PB and index dividend-yield return single values only; their output omits percentile, lookback years, sample count, and sample start date.
PB returns the current value only and uses the SW index analysis source. It requires `--category`: `市场表征`, `一级行业`, `二级行业`, or `风格指数`; `--code` must be an SW index code in that category, such as `801010` for `一级行业`, not a CSIndex code such as `000300`.

## Database

By default, data is stored at:

```text
~/.finance-cli/finance.db
```

Override the path with:

```bash
FINANCE_CLI_DB=/path/to/finance.db finance gold
```
