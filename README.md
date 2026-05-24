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
`NDX` uses Danjuan's historical valuation API and is also stored as `rolling_pe`.
`VN30` uses WorldPEratio monthly historical P/E data and is also stored as `rolling_pe`; `VN30` is based on WorldPEratio's Vietnam market series.

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

Query fund net asset value:

```bash
finance fund-nav --code 017763
finance fund-nav --code 017763 --date 2026-05-22
finance fund-nav --code 017763 --nav-type accumulated
```

Fund NAV uses Eastmoney/Tiantian Fund historical NAV data via akshare.
`--nav-type` supports `unit` and `accumulated`; it defaults to `unit`.
It returns the current value only; it does not calculate a historical percentile.

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

Query date ranges:

```bash
finance pe --code 000300 --from 2026-01-01 --to 2026-05-01 --json
finance dividend-yield --code 000300 --from 2026-01-01 --to 2026-05-01 --json
finance pb --code 930707 --from 2026-01-01 --to 2026-05-01 --json
finance pb --code 801010 --category 一级行业 --from 2026-01-01 --to 2026-05-01 --json
finance gold --from 2026-01-01 --to 2026-05-01 --json
finance cn10y-yield --from 2026-01-01 --to 2026-05-01 --json
finance fund-nav --code 017763 --from 2026-01-01 --to 2026-05-01 --json
finance fund-nav --code 017763 --nav-type accumulated --from 2026-01-01 --to 2026-05-01 --json
```

Range JSON includes `requested_from`, `requested_to`, `actual_start_date`, `actual_end_date`, and `data`.
Each `data` row contains `date`, `value`, and `source`.
Range output returns raw values only; it never includes percentile, sample count, sample start date, lookback years, coverage status, or effective years.

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
Fund NAV also returns a single value only and omits percentile, lookback years, sample count, and sample start date.
PB returns the current value only. Without `--category`, CSI `9xxxxx` index codes such as `930707` use ETF.run's latest PB page. With `--category`, PB uses the SW index analysis source; `--category` must be `市场表征`, `一级行业`, `二级行业`, or `风格指数`, and `--code` must be an SW index code in that category, such as `801010` for `一级行业`.

## Database

Data is stored in the SQLite API service. The default local config is:

```json
{
  "sqlite_api_host": "http://192.168.3.56:8080",
  "sqlite_db": "finance.db"
}
```

Override the config file with:

```bash
FINANCE_CLI_CONFIG=/path/to/config.json finance gold
```

When deployed to the server, `scripts/deploy_to_server.sh` writes a server config using
`http://127.0.0.1:8080`.
