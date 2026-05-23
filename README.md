# finance-cli

Financial data CLI backed by SQLite, akshare, and selected public web sources.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Commands

Query index rolling PE percentile:

```bash
finance pe --code 000300 --date 2026-04-20 --years 10
finance pe --code H30269 --years 10
finance pe --code 990001 --years 10
finance pe --code NDX --years 10
finance pe --code VN30 --years 10
```

Rolling PE uses the CSIndex historical `滚动市盈率` field and is stored as `rolling_pe`.
`NDX` and `VN30` use WorldPEratio monthly historical P/E data and are also stored as `rolling_pe`; `VN30` is based on WorldPEratio's Vietnam market series.

Query index dividend-yield value:

```bash
finance dividend-yield --code 000300 --date 2026-04-20
finance dividend-yield --code H30269
```

Index dividend-yield uses the CSIndex indicator `股息率2（计算用股本）D/P2` field.
It returns the current value only; it does not calculate a historical percentile.

Query index PB value:

```bash
finance pb --code 930707
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
For index PE, if the requested 10-year window is unavailable but at least 3 years of history exists, the percentile uses all available data and the output marks the sample as partial coverage.
PB and index dividend-yield return single values only; their output omits percentile, lookback years, sample count, and sample start date.
PB returns the current value only. Without `--category`, CSI `9xxxxx` index codes such as `930707` use ETF.run's latest PB page. With `--category`, PB uses the SW index analysis source; `--category` must be `市场表征`, `一级行业`, `二级行业`, or `风格指数`, and `--code` must be an SW index code in that category, such as `801010` for `一级行业`.

## Database

By default, data is stored at:

```text
~/.finance-cli/finance.db
```

Override the path with:

```bash
FINANCE_CLI_DB=/path/to/finance.db finance gold
```
