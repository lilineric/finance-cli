# Fund Info CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fund profile CLI commands that query cached remote SQLite data first, fetch and store akshare fund info when needed, force refresh on request, and support manual JSON updates.

**Architecture:** Add a dedicated `fund_info` snapshot table and `FundInfo` model beside the existing `daily_metrics` series model. Keep responsibilities aligned with the current codebase: repository handles SQLite API payloads, service handles cache/refresh/manual flows, sources normalize akshare DataFrames, output formats response models, and CLI wires commands plus parameter validation.

**Tech Stack:** Python 3.11, Typer, pandas, akshare, remote SQLite API, pytest.

---

## File Structure

- Modify `src/finance_cli/db.py`: add `FundInfo` dataclass, create `fund_info` schema during `MetricsRepository.initialize`, and add `fund_info_by_code` / `upsert_fund_info`.
- Modify `src/finance_cli/service.py`: add service methods for cached query, forced refresh, manual upsert, and fallback-to-cache-on-source-failure.
- Modify `src/finance_cli/sources.py`: add `fetch_fund_info`, fund profile normalization, fee tier parsing, and manual payload validation helpers if they belong near source normalization.
- Modify `src/finance_cli/output.py`: add JSON and text formatters for `FundInfo`.
- Modify `src/finance_cli/cli.py`: add `fund-info` and `fund-info-update` commands, data/file input validation, and error mapping.
- Modify `tests/test_db.py`: repository schema and fund info mapping tests.
- Modify `tests/test_service.py`: cache, refresh, fallback, and manual upsert behavior tests.
- Modify `tests/test_sources.py`: fund profile normalization and fee tier parsing tests.
- Modify `tests/test_output.py`: fund info JSON/text formatting tests.
- Modify `tests/test_cli.py`: command shape, JSON/file update, and validation tests.
- Modify `README.md`: document command usage and JSON format.

Keep existing `fund-nav` behavior unchanged.

---

### Task 1: Repository Model And Persistence

**Files:**
- Modify: `src/finance_cli/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing repository tests**

Add these tests to `tests/test_db.py`:

```python
def test_repository_initialize_creates_fund_info_schema():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    repo.initialize()

    schema_sql = "\n".join(call[1]["sql"] for call in client.calls if call[0] == "/v1/sqlite/exec")
    assert "CREATE TABLE IF NOT EXISTS daily_metrics" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS fund_info" in schema_sql
    assert "purchase_fee_json TEXT NOT NULL" in schema_sql
    assert "redemption_fee_json TEXT NOT NULL" in schema_sql


def test_repository_upserts_fund_info():
    client = FakeSQLiteApiClient()
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    inserted = repo.upsert_fund_info(
        FundInfo(
            code="017763",
            name="银河领先债券C",
            fund_type="债券型",
            established_date="2023-01-01",
            asset_size="10.25亿元",
            purchase_status="开放申购",
            redemption_status="开放赎回",
            morningstar_rating="5",
            purchase_fee=[
                {
                    "min_amount": 0,
                    "max_amount": 1000000,
                    "original_rate": 0.015,
                    "discounted_rate": 0.0015,
                }
            ],
            redemption_fee=[
                {
                    "min_holding_days": 0,
                    "max_holding_days": 7,
                    "original_rate": 0.015,
                    "discounted_rate": 0.015,
                }
            ],
            source="manual",
            updated_at="2026-06-07T12:00:00+00:00",
        )
    )

    assert inserted == 1
    path, payload = client.calls[0]
    assert path == "/v1/sqlite/exec"
    assert payload["db"] == "finance.db"
    assert "INSERT INTO fund_info" in payload["sql"]
    assert "ON CONFLICT(code) DO UPDATE SET" in payload["sql"]
    assert payload["params"][0:9] == [
        "017763",
        "银河领先债券C",
        "债券型",
        "2023-01-01",
        "10.25亿元",
        "开放申购",
        "开放赎回",
        "5",
        '[{"min_amount":0,"max_amount":1000000,"original_rate":0.015,"discounted_rate":0.0015}]',
    ]
    assert payload["params"][9] == (
        '[{"min_holding_days":0,"max_holding_days":7,"original_rate":0.015,"discounted_rate":0.015}]'
    )
    assert payload["params"][10:12] == ["manual", "2026-06-07T12:00:00+00:00"]


def test_repository_queries_fund_info_by_code():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": {
                "columns": [
                    "code",
                    "name",
                    "fund_type",
                    "established_date",
                    "asset_size",
                    "purchase_status",
                    "redemption_status",
                    "morningstar_rating",
                    "purchase_fee_json",
                    "redemption_fee_json",
                    "source",
                    "updated_at",
                ],
                "rows": [
                    [
                        "017763",
                        "银河领先债券C",
                        "债券型",
                        "2023-01-01",
                        "10.25亿元",
                        "开放申购",
                        "开放赎回",
                        "5",
                        '[{"min_amount":0,"max_amount":1000000,"original_rate":0.015,"discounted_rate":0.0015}]',
                        '[{"min_holding_days":0,"max_holding_days":7,"original_rate":0.015,"discounted_rate":0.015}]',
                        "akshare",
                        "2026-06-07T12:00:00+00:00",
                    ]
                ],
                "row_count": 1,
            }
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    result = repo.fund_info_by_code("017763")

    assert result == FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            }
        ],
        redemption_fee=[
            {
                "min_holding_days": 0,
                "max_holding_days": 7,
                "original_rate": 0.015,
                "discounted_rate": 0.015,
            }
        ],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
    )
    assert client.calls[0][0] == "/v1/sqlite/query"
    assert client.calls[0][1]["params"] == ["017763"]


def test_repository_returns_none_for_missing_fund_info():
    client = FakeSQLiteApiClient(
        {
            "/v1/sqlite/query": {
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        }
    )
    repo = MetricsRepository("http://api.example", "finance.db", client=client)

    assert repo.fund_info_by_code("017763") is None
```

Update the import at the top of `tests/test_db.py`:

```python
from finance_cli.db import DailyMetric, FundInfo, MetricsRepository, SQLiteApiError
```

- [ ] **Step 2: Run repository tests and verify they fail**

Run:

```bash
pytest tests/test_db.py -v
```

Expected: FAIL with `ImportError` or `AttributeError` for `FundInfo`, `upsert_fund_info`, and `fund_info_by_code`.

- [ ] **Step 3: Implement repository model and methods**

In `src/finance_cli/db.py`, add this dataclass after `DailyMetric`:

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
    purchase_fee: list[dict[str, Any]]
    redemption_fee: list[dict[str, Any]]
    source: str
    updated_at: str
```

In `MetricsRepository.initialize`, add a second `/v1/sqlite/exec` call after the existing `daily_metrics` schema creation:

```python
self.client.post_json(
    "/v1/sqlite/exec",
    {
        "db": self.db_name,
        "sql": """
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
        """,
        "params": [],
    },
)
```

Add these methods to `MetricsRepository`:

```python
def upsert_fund_info(self, fund_info: FundInfo) -> int:
    response = self.client.post_json(
        "/v1/sqlite/exec",
        {
            "db": self.db_name,
            "sql": """
            INSERT INTO fund_info (
                code,
                name,
                fund_type,
                established_date,
                asset_size,
                purchase_status,
                redemption_status,
                morningstar_rating,
                purchase_fee_json,
                redemption_fee_json,
                source,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                fund_type = excluded.fund_type,
                established_date = excluded.established_date,
                asset_size = excluded.asset_size,
                purchase_status = excluded.purchase_status,
                redemption_status = excluded.redemption_status,
                morningstar_rating = excluded.morningstar_rating,
                purchase_fee_json = excluded.purchase_fee_json,
                redemption_fee_json = excluded.redemption_fee_json,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            "params": [
                fund_info.code,
                fund_info.name,
                fund_info.fund_type,
                fund_info.established_date,
                fund_info.asset_size,
                fund_info.purchase_status,
                fund_info.redemption_status,
                fund_info.morningstar_rating,
                _compact_json(fund_info.purchase_fee),
                _compact_json(fund_info.redemption_fee),
                fund_info.source,
                fund_info.updated_at,
            ],
        },
    )
    return int(response.get("rows_affected", 0))

def fund_info_by_code(self, code: str) -> FundInfo | None:
    response = self.client.post_json(
        "/v1/sqlite/query",
        {
            "db": self.db_name,
            "sql": """
            SELECT
                code,
                name,
                fund_type,
                established_date,
                asset_size,
                purchase_status,
                redemption_status,
                morningstar_rating,
                purchase_fee_json,
                redemption_fee_json,
                source,
                updated_at
            FROM fund_info
            WHERE code = ?
            LIMIT 1
            """,
            "params": [code],
        },
    )
    rows = response.get("rows", [])
    if not rows:
        return None

    columns = response.get("columns", [])
    row = dict(zip(columns, rows[0], strict=True))
    return FundInfo(
        code=str(row["code"]),
        name=str(row["name"]),
        fund_type=_optional_str(row["fund_type"]),
        established_date=_optional_str(row["established_date"]),
        asset_size=_optional_str(row["asset_size"]),
        purchase_status=_optional_str(row["purchase_status"]),
        redemption_status=_optional_str(row["redemption_status"]),
        morningstar_rating=_optional_str(row["morningstar_rating"]),
        purchase_fee=_decode_json_list(row["purchase_fee_json"]),
        redemption_fee=_decode_json_list(row["redemption_fee_json"]),
        source=str(row["source"]),
        updated_at=str(row["updated_at"]),
    )
```

Add these helpers near `_decode_json_response`:

```python
def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode_json_list(value: Any) -> list[dict[str, Any]]:
    decoded = json.loads(str(value))
    if not isinstance(decoded, list):
        raise ValueError("stored fund fee JSON must be a list")
    return decoded


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
```

- [ ] **Step 4: Run repository tests and verify they pass**

Run:

```bash
pytest tests/test_db.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit repository layer**

Run:

```bash
git add src/finance_cli/db.py tests/test_db.py
git commit -m "feat: add fund info repository storage"
```

Expected: commit succeeds. Do not stage unrelated pre-existing worktree changes.

---

### Task 2: Service Cache, Refresh, And Manual Upsert

**Files:**
- Modify: `src/finance_cli/service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write failing service tests**

Add `FundInfo` to the import in `tests/test_service.py`:

```python
from finance_cli.db import DailyMetric, FundInfo
```

Add this fake repository class near the existing service test fakes:

```python
class FakeFundInfoRepository:
    def __init__(self, existing=None):
        self.existing = existing
        self.initialize_calls = 0
        self.query_calls = []
        self.upserts = []

    def initialize(self):
        self.initialize_calls += 1

    def fund_info_by_code(self, code):
        self.query_calls.append(code)
        return self.existing

    def upsert_fund_info(self, fund_info):
        self.existing = fund_info
        self.upserts.append(fund_info)
        return 1
```

Add these tests:

```python
def _fund_info(source="akshare", updated_at="2026-06-07T12:00:00+00:00"):
    return FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[],
        redemption_fee=[],
        source=source,
        updated_at=updated_at,
    )


def test_query_fund_info_returns_cached_data_without_fetching():
    cached = _fund_info(source="manual")
    repo = FakeFundInfoRepository(existing=cached)
    service = MetricsService(repo)
    called = False

    def fetch_missing():
        nonlocal called
        called = True
        return _fund_info()

    result = service.query_fund_info("017763", fetch_missing)

    assert result == cached
    assert called is False
    assert repo.initialize_calls == 1
    assert repo.upserts == []


def test_query_fund_info_fetches_and_upserts_when_cache_missing():
    repo = FakeFundInfoRepository(existing=None)
    service = MetricsService(repo)
    fresh = _fund_info()

    result = service.query_fund_info("017763", lambda: fresh)

    assert result == fresh
    assert repo.upserts == [fresh]


def test_query_fund_info_refresh_fetches_even_when_cache_exists():
    cached = _fund_info(source="manual")
    fresh = _fund_info(source="akshare", updated_at="2026-06-07T13:00:00+00:00")
    repo = FakeFundInfoRepository(existing=cached)
    service = MetricsService(repo)

    result = service.query_fund_info("017763", lambda: fresh, refresh=True)

    assert result == fresh
    assert repo.upserts == [fresh]


def test_query_fund_info_returns_cached_data_when_default_fetch_fails():
    cached = _fund_info(source="manual")
    repo = FakeFundInfoRepository(existing=cached)
    repo.existing = None
    service = MetricsService(repo)

    def fetch_missing():
        repo.existing = cached
        raise DataSourceError("akshare unavailable")

    result = service.query_fund_info("017763", fetch_missing)

    assert result == cached
    assert repo.upserts == []


def test_query_fund_info_refresh_fetch_failure_does_not_return_cached_data():
    cached = _fund_info(source="manual")
    repo = FakeFundInfoRepository(existing=cached)
    service = MetricsService(repo)

    def fetch_missing():
        raise DataSourceError("akshare unavailable")

    with pytest.raises(DataSourceError, match="akshare unavailable"):
        service.query_fund_info("017763", fetch_missing, refresh=True)

    assert repo.upserts == []


def test_update_fund_info_initializes_and_upserts():
    fund_info = _fund_info(source="manual")
    repo = FakeFundInfoRepository()
    service = MetricsService(repo)

    result = service.update_fund_info(fund_info)

    assert result == fund_info
    assert repo.initialize_calls == 1
    assert repo.upserts == [fund_info]
```

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```bash
pytest tests/test_service.py -v
```

Expected: FAIL with `AttributeError` for `query_fund_info` and `update_fund_info`.

- [ ] **Step 3: Implement service methods**

In `src/finance_cli/service.py`, update the import:

```python
from finance_cli.db import DailyMetric, FundInfo, MetricsRepository
```

Add these methods to `MetricsService`:

```python
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
```

- [ ] **Step 4: Run service tests and verify they pass**

Run:

```bash
pytest tests/test_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit service layer**

Run:

```bash
git add src/finance_cli/service.py tests/test_service.py
git commit -m "feat: add fund info service flow"
```

Expected: commit succeeds.

---

### Task 3: Fund Info Output Formatters

**Files:**
- Modify: `src/finance_cli/output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write failing output tests**

Update imports in `tests/test_output.py`:

```python
from finance_cli.db import FundInfo
```

Add these tests:

```python
def test_format_fund_info_json_outputs_expected_payload():
    fund_info = FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            }
        ],
        redemption_fee=[
            {
                "min_holding_days": 0,
                "max_holding_days": None,
                "original_rate": 0,
                "discounted_rate": 0,
            }
        ],
        source="akshare",
        updated_at="2026-06-07T12:00:00+00:00",
    )

    payload = json.loads(format_fund_info_json(fund_info))

    assert payload["code"] == "017763"
    assert payload["name"] == "银河领先债券C"
    assert payload["purchase_fee"][0]["discounted_rate"] == 0.0015
    assert payload["redemption_fee"][0]["max_holding_days"] is None
    assert payload["source"] == "akshare"


def test_format_fund_info_text_outputs_chinese_labels_and_fee_tiers():
    fund_info = FundInfo(
        code="017763",
        name="银河领先债券C",
        fund_type="债券型",
        established_date="2023-01-01",
        asset_size="10.25亿元",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        morningstar_rating="5",
        purchase_fee=[
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            },
            {
                "min_amount": 1000000,
                "max_amount": None,
                "original_rate": None,
                "discounted_rate": None,
                "fixed_fee": 1000,
            },
        ],
        redemption_fee=[
            {
                "min_holding_days": 0,
                "max_holding_days": 7,
                "original_rate": 0.015,
                "discounted_rate": 0.015,
            }
        ],
        source="manual",
        updated_at="2026-06-07T12:00:00+00:00",
    )

    text = format_fund_info_text(fund_info)

    assert "基金: 017763" in text
    assert "基金名称: 银河领先债券C" in text
    assert "晨星评级: 5" in text
    assert "申购费率:" in text
    assert "0 <= amount < 1000000: 原费率 1.5%, 折扣后费率 0.15%" in text
    assert "amount >= 1000000: 固定费用 1000元" in text
    assert "赎回费率:" in text
    assert "0 <= days < 7: 原费率 1.5%, 折扣后费率 1.5%" in text
```

Add `format_fund_info_json` and `format_fund_info_text` to the existing output imports in the test file.

- [ ] **Step 2: Run output tests and verify they fail**

Run:

```bash
pytest tests/test_output.py -v
```

Expected: FAIL with `ImportError` for the new formatters.

- [ ] **Step 3: Implement output formatters**

In `src/finance_cli/output.py`, update imports:

```python
from finance_cli.db import FundInfo
```

Add these functions:

```python
def format_fund_info_json(result: FundInfo) -> str:
    return json.dumps(
        {
            "code": result.code,
            "name": result.name,
            "fund_type": result.fund_type,
            "established_date": result.established_date,
            "asset_size": result.asset_size,
            "purchase_status": result.purchase_status,
            "redemption_status": result.redemption_status,
            "morningstar_rating": result.morningstar_rating,
            "purchase_fee": result.purchase_fee,
            "redemption_fee": result.redemption_fee,
            "source": result.source,
            "updated_at": result.updated_at,
        },
        ensure_ascii=False,
    )


def format_fund_info_text(result: FundInfo) -> str:
    lines = [
        f"基金: {result.code}",
        f"基金名称: {result.name}",
        f"基金类型: {_display_value(result.fund_type)}",
        f"成立日期: {_display_value(result.established_date)}",
        f"资产规模: {_display_value(result.asset_size)}",
        f"申购状态: {_display_value(result.purchase_status)}",
        f"赎回状态: {_display_value(result.redemption_status)}",
        f"晨星评级: {_display_value(result.morningstar_rating)}",
        f"数据源: {result.source}",
        f"更新时间: {result.updated_at}",
        "申购费率:",
    ]
    lines.extend(_purchase_fee_lines(result.purchase_fee))
    lines.append("赎回费率:")
    lines.extend(_redemption_fee_lines(result.redemption_fee))
    return "\n".join(lines)


def _display_value(value: object) -> str:
    return "未知" if value is None else str(value)


def _purchase_fee_lines(fee_tiers: list[dict[str, object]]) -> list[str]:
    if not fee_tiers:
        return ["无"]
    return [_format_purchase_fee_tier(tier) for tier in fee_tiers]


def _redemption_fee_lines(fee_tiers: list[dict[str, object]]) -> list[str]:
    if not fee_tiers:
        return ["无"]
    return [_format_redemption_fee_tier(tier) for tier in fee_tiers]


def _format_purchase_fee_tier(tier: dict[str, object]) -> str:
    min_amount = tier["min_amount"]
    max_amount = tier.get("max_amount")
    if max_amount is None:
        range_text = f"amount >= {min_amount}"
    else:
        range_text = f"{min_amount} <= amount < {max_amount}"
    return f"{range_text}: {_format_fee_value(tier)}"


def _format_redemption_fee_tier(tier: dict[str, object]) -> str:
    min_days = tier["min_holding_days"]
    max_days = tier.get("max_holding_days")
    if max_days is None:
        range_text = f"days >= {min_days}"
    else:
        range_text = f"{min_days} <= days < {max_days}"
    return f"{range_text}: {_format_fee_value(tier)}"


def _format_fee_value(tier: dict[str, object]) -> str:
    fixed_fee = tier.get("fixed_fee")
    if fixed_fee is not None:
        return f"固定费用 {fixed_fee}元"
    return (
        f"原费率 {_format_rate(tier.get('original_rate'))}, "
        f"折扣后费率 {_format_rate(tier.get('discounted_rate'))}"
    )


def _format_rate(value: object) -> str:
    if value is None:
        return "未知"
    percentage = float(value) * 100
    return f"{percentage:g}%"
```

- [ ] **Step 4: Run output tests and verify they pass**

Run:

```bash
pytest tests/test_output.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit output layer**

Run:

```bash
git add src/finance_cli/output.py tests/test_output.py
git commit -m "feat: format fund info output"
```

Expected: commit succeeds.

---

### Task 4: Source Normalization And Fee Parsing

**Files:**
- Modify: `src/finance_cli/sources.py`
- Test: `tests/test_sources.py`

- [ ] **Step 1: Write failing source normalization tests**

Update the imports in `tests/test_sources.py`:

```python
from finance_cli.sources import (
    DataSourceError,
    fetch_fund_info,
    normalize_fund_code,
    normalize_fund_info,
    normalize_purchase_fee_rows,
    normalize_redemption_fee_rows,
)
```

Keep existing imports in place and add missing names without removing unrelated imports.

Add these tests:

```python
def test_normalize_purchase_fee_rows_parses_amount_tiers_and_discount_rates():
    frame = pd.DataFrame(
        {
            "适用金额": ["小于100万元", "大于等于100万元"],
            "原费率": ["1.50%", "1000元/笔"],
            "天天基金优惠费率": ["0.15%", "1000元/笔"],
        }
    )

    tiers = normalize_purchase_fee_rows(frame)

    assert tiers == [
        {
            "min_amount": 0,
            "max_amount": 1000000,
            "original_rate": 0.015,
            "discounted_rate": 0.0015,
        },
        {
            "min_amount": 1000000,
            "max_amount": None,
            "original_rate": None,
            "discounted_rate": None,
            "fixed_fee": 1000,
        },
    ]


def test_normalize_redemption_fee_rows_parses_holding_period_tiers():
    frame = pd.DataFrame(
        {
            "持有期限": ["小于7天", "大于等于730天"],
            "赎回费率": ["1.50%", "0.00%"],
        }
    )

    tiers = normalize_redemption_fee_rows(frame)

    assert tiers == [
        {
            "min_holding_days": 0,
            "max_holding_days": 7,
            "original_rate": 0.015,
            "discounted_rate": 0.015,
        },
        {
            "min_holding_days": 730,
            "max_holding_days": None,
            "original_rate": 0,
            "discounted_rate": 0,
        },
    ]


def test_normalize_purchase_fee_rows_rejects_unparseable_tier():
    frame = pd.DataFrame(
        {
            "适用金额": ["详见基金公告"],
            "原费率": ["1.50%"],
            "天天基金优惠费率": ["0.15%"],
        }
    )

    with pytest.raises(DataSourceError, match="Failed to parse purchase fee tier"):
        normalize_purchase_fee_rows(frame)


def test_normalize_fund_info_combines_profile_status_fees_and_rating():
    basic_frame = pd.DataFrame(
        {
            "item": ["基金名称", "基金类型", "成立日期", "资产规模"],
            "value": ["银河领先债券C", "债券型", "2023-01-01", "10.25亿元"],
        }
    )
    purchase_status_frame = pd.DataFrame(
        {
            "基金代码": ["017763"],
            "申购状态": ["开放申购"],
            "赎回状态": ["开放赎回"],
        }
    )
    purchase_fee_frame = pd.DataFrame(
        {
            "适用金额": ["小于100万元"],
            "原费率": ["1.50%"],
            "天天基金优惠费率": ["0.15%"],
        }
    )
    redemption_fee_frame = pd.DataFrame(
        {
            "持有期限": ["小于7天"],
            "赎回费率": ["1.50%"],
        }
    )
    rating_frame = pd.DataFrame(
        {
            "代码": ["017763"],
            "晨星评级": ["5"],
        }
    )

    result = normalize_fund_info(
        "017763",
        basic_frame,
        purchase_status_frame,
        purchase_fee_frame,
        redemption_fee_frame,
        rating_frame,
        updated_at="2026-06-07T12:00:00+00:00",
    )

    assert result.code == "017763"
    assert result.name == "银河领先债券C"
    assert result.fund_type == "债券型"
    assert result.established_date == "2023-01-01"
    assert result.asset_size == "10.25亿元"
    assert result.purchase_status == "开放申购"
    assert result.redemption_status == "开放赎回"
    assert result.morningstar_rating == "5"
    assert result.purchase_fee[0]["discounted_rate"] == 0.0015
    assert result.redemption_fee[0]["original_rate"] == 0.015
    assert result.source == "akshare"
    assert result.updated_at == "2026-06-07T12:00:00+00:00"
```

- [ ] **Step 2: Run source tests and verify they fail**

Run:

```bash
pytest tests/test_sources.py -v
```

Expected: FAIL with `ImportError` for `normalize_fund_info`, `normalize_purchase_fee_rows`, and `normalize_redemption_fee_rows`.

- [ ] **Step 3: Implement source normalization helpers**

In `src/finance_cli/sources.py`, update the DB import:

```python
from finance_cli.db import DailyMetric, FundInfo
```

Add constants near the existing fund constants:

```python
FUND_BASIC_KEY_COLUMNS = ("item", "项目", "字段", "名称")
FUND_BASIC_VALUE_COLUMNS = ("value", "内容", "值")
FUND_CODE_COLUMNS = ("基金代码", "代码", "fund_code", "code")
FUND_NAME_KEYS = ("基金名称", "name")
FUND_TYPE_KEYS = ("基金类型", "类型", "fund_type")
FUND_ESTABLISHED_DATE_KEYS = ("成立日期", "established_date")
FUND_ASSET_SIZE_KEYS = ("资产规模", "asset_size")
FUND_PURCHASE_STATUS_COLUMNS = ("申购状态", "purchase_status")
FUND_REDEMPTION_STATUS_COLUMNS = ("赎回状态", "redemption_status")
FUND_RATING_COLUMNS = ("晨星评级", "晨星评级(三年)", "morningstar_rating")
PURCHASE_AMOUNT_COLUMNS = ("适用金额", "金额", "amount_range")
PURCHASE_ORIGINAL_RATE_COLUMNS = ("原费率", "费率", "original_rate")
PURCHASE_DISCOUNTED_RATE_COLUMNS = ("天天基金优惠费率", "优惠费率", "discounted_rate")
REDEMPTION_HOLDING_COLUMNS = ("持有期限", "持有时间", "holding_period")
REDEMPTION_RATE_COLUMNS = ("赎回费率", "费率", "redemption_rate")
```

Add these functions:

```python
def normalize_purchase_fee_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    amount_column = _first_existing_column(frame, PURCHASE_AMOUNT_COLUMNS)
    original_rate_column = _first_existing_column(frame, PURCHASE_ORIGINAL_RATE_COLUMNS)
    discounted_rate_column = _first_existing_column(frame, PURCHASE_DISCOUNTED_RATE_COLUMNS)
    tiers = []
    for _, row in frame.iterrows():
        amount_text = str(row[amount_column]).strip()
        original_text = str(row[original_rate_column]).strip()
        discounted_text = str(row[discounted_rate_column]).strip()
        try:
            tier = _parse_amount_range(amount_text)
            fee_value = _parse_purchase_fee_value(original_text, discounted_text)
        except DataSourceError as exc:
            raise DataSourceError(f"Failed to parse purchase fee tier: {amount_text}") from exc
        tiers.append({**tier, **fee_value})
    return sorted(tiers, key=lambda item: float(item["min_amount"]))


def normalize_redemption_fee_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame.empty:
        return []
    holding_column = _first_existing_column(frame, REDEMPTION_HOLDING_COLUMNS)
    rate_column = _first_existing_column(frame, REDEMPTION_RATE_COLUMNS)
    tiers = []
    for _, row in frame.iterrows():
        holding_text = str(row[holding_column]).strip()
        rate_text = str(row[rate_column]).strip()
        try:
            tier = _parse_holding_period_range(holding_text)
            rate = _parse_rate(rate_text)
        except DataSourceError as exc:
            raise DataSourceError(f"Failed to parse redemption fee tier: {holding_text}") from exc
        tiers.append(
            {
                **tier,
                "original_rate": rate,
                "discounted_rate": rate,
            }
        )
    return sorted(tiers, key=lambda item: int(item["min_holding_days"]))


def normalize_fund_info(
    code: str,
    basic_frame: pd.DataFrame,
    purchase_status_frame: pd.DataFrame,
    purchase_fee_frame: pd.DataFrame,
    redemption_fee_frame: pd.DataFrame,
    rating_frame: pd.DataFrame,
    updated_at: str,
) -> FundInfo:
    normalized_code = normalize_fund_code(code)
    basic = _fund_basic_mapping(basic_frame)
    name = _first_mapping_value(basic, FUND_NAME_KEYS)
    if name is None:
        raise DataSourceError(f"No fund name found for {normalized_code}")
    status_row = _row_for_code(purchase_status_frame, normalized_code)
    rating_row = _row_for_code(rating_frame, normalized_code)
    return FundInfo(
        code=normalized_code,
        name=name,
        fund_type=_first_mapping_value(basic, FUND_TYPE_KEYS),
        established_date=_first_mapping_value(basic, FUND_ESTABLISHED_DATE_KEYS),
        asset_size=_first_mapping_value(basic, FUND_ASSET_SIZE_KEYS),
        purchase_status=_first_row_value(status_row, FUND_PURCHASE_STATUS_COLUMNS),
        redemption_status=_first_row_value(status_row, FUND_REDEMPTION_STATUS_COLUMNS),
        morningstar_rating=_first_row_value(rating_row, FUND_RATING_COLUMNS),
        purchase_fee=normalize_purchase_fee_rows(purchase_fee_frame),
        redemption_fee=normalize_redemption_fee_rows(redemption_fee_frame),
        source="akshare",
        updated_at=updated_at,
    )
```

Add parsing helpers below the new functions:

```python
def _fund_basic_mapping(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty:
        return {}
    key_column = _first_existing_column(frame, FUND_BASIC_KEY_COLUMNS)
    value_column = _first_existing_column(frame, FUND_BASIC_VALUE_COLUMNS)
    return {
        str(row[key_column]).strip(): str(row[value_column]).strip()
        for _, row in frame.iterrows()
        if not _is_missing(row[value_column])
    }


def _first_mapping_value(mapping: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in mapping and mapping[key]:
            return mapping[key]
    return None


def _row_for_code(frame: pd.DataFrame, code: str) -> pd.Series | None:
    if frame.empty:
        return None
    code_column = _first_existing_column(frame, FUND_CODE_COLUMNS)
    matched = frame[frame[code_column].astype(str).str.zfill(6) == code]
    if matched.empty:
        return None
    return matched.iloc[0]


def _first_row_value(row: pd.Series | None, columns: tuple[str, ...]) -> str | None:
    if row is None:
        return None
    for column in columns:
        if column in row.index and not _is_missing(row[column]):
            return str(row[column]).strip()
    return None


def _parse_amount_range(text: str) -> dict[str, int | None]:
    normalized = text.replace(",", "").replace("，", "").replace(" ", "")
    if match := re.fullmatch(r"(?:小于|少于|低于)(\d+(?:\.\d+)?)(万)?元?", normalized):
        return {"min_amount": 0, "max_amount": _amount_to_yuan(match.group(1), match.group(2))}
    if match := re.fullmatch(r"(?:大于等于|不少于|>=)(\d+(?:\.\d+)?)(万)?元?", normalized):
        return {"min_amount": _amount_to_yuan(match.group(1), match.group(2)), "max_amount": None}
    if match := re.fullmatch(
        r"(\d+(?:\.\d+)?)(万)?元?(?:<=|≤)(?:申购金额|金额)<(\d+(?:\.\d+)?)(万)?元?",
        normalized,
    ):
        return {
            "min_amount": _amount_to_yuan(match.group(1), match.group(2)),
            "max_amount": _amount_to_yuan(match.group(3), match.group(4)),
        }
    raise DataSourceError(f"Unparseable amount range: {text}")


def _parse_holding_period_range(text: str) -> dict[str, int | None]:
    normalized = text.replace(" ", "")
    if match := re.fullmatch(r"(?:小于|少于|低于)(\d+)天", normalized):
        return {"min_holding_days": 0, "max_holding_days": int(match.group(1))}
    if match := re.fullmatch(r"(?:大于等于|不少于|>=)(\d+)天", normalized):
        return {"min_holding_days": int(match.group(1)), "max_holding_days": None}
    if match := re.fullmatch(r"(\d+)天(?:<=|≤)(?:持有期限|持有时间)<(\d+)天", normalized):
        return {"min_holding_days": int(match.group(1)), "max_holding_days": int(match.group(2))}
    if match := re.fullmatch(r"(?:大于等于|不少于|>=)(\d+)年", normalized):
        return {"min_holding_days": int(match.group(1)) * 365, "max_holding_days": None}
    raise DataSourceError(f"Unparseable holding period: {text}")


def _parse_purchase_fee_value(original_text: str, discounted_text: str) -> dict[str, float | int | None]:
    fixed_fee = _parse_fixed_fee(original_text)
    if fixed_fee is not None:
        return {
            "original_rate": None,
            "discounted_rate": None,
            "fixed_fee": fixed_fee,
        }
    return {
        "original_rate": _parse_rate(original_text),
        "discounted_rate": _parse_rate(discounted_text),
    }


def _parse_rate(text: str) -> float:
    normalized = text.strip()
    if normalized in {"0", "0.00%", "免费"}:
        return 0
    if match := re.fullmatch(r"(\d+(?:\.\d+)?)%", normalized):
        return float(match.group(1)) / 100
    raise DataSourceError(f"Unparseable rate: {text}")


def _parse_fixed_fee(text: str) -> int | None:
    normalized = text.strip()
    if match := re.fullmatch(r"(\d+)元(?:/笔)?", normalized):
        return int(match.group(1))
    return None


def _amount_to_yuan(number_text: str, unit: str | None) -> int:
    value = float(number_text)
    if unit == "万":
        value *= 10000
    return int(value)
```

- [ ] **Step 4: Run source tests and verify new normalization tests pass**

Run:

```bash
pytest tests/test_sources.py::test_normalize_purchase_fee_rows_parses_amount_tiers_and_discount_rates tests/test_sources.py::test_normalize_redemption_fee_rows_parses_holding_period_tiers tests/test_sources.py::test_normalize_purchase_fee_rows_rejects_unparseable_tier tests/test_sources.py::test_normalize_fund_info_combines_profile_status_fees_and_rating -v
```

Expected: PASS.

- [ ] **Step 5: Commit source normalization**

Run:

```bash
git add src/finance_cli/sources.py tests/test_sources.py
git commit -m "feat: normalize fund info sources"
```

Expected: commit succeeds.

---

### Task 5: akshare Fund Info Fetch Aggregation

**Files:**
- Modify: `src/finance_cli/sources.py`
- Test: `tests/test_sources.py`

- [ ] **Step 1: Write failing fetch aggregation test**

Add this test to `tests/test_sources.py`:

```python
def test_fetch_fund_info_aggregates_akshare_frames():
    calls = []

    def basic_fetcher(symbol):
        calls.append(("basic", symbol))
        return pd.DataFrame(
            {
                "item": ["基金名称", "基金类型", "成立日期", "资产规模"],
                "value": ["银河领先债券C", "债券型", "2023-01-01", "10.25亿元"],
            }
        )

    def purchase_fetcher():
        calls.append(("purchase_status", None))
        return pd.DataFrame(
            {
                "基金代码": ["017763"],
                "申购状态": ["开放申购"],
                "赎回状态": ["开放赎回"],
            }
        )

    def fee_fetcher(symbol, indicator):
        calls.append(("fee", symbol, indicator))
        if indicator == "申购费率（前端）":
            return pd.DataFrame(
                {
                    "适用金额": ["小于100万元"],
                    "原费率": ["1.50%"],
                    "天天基金优惠费率": ["0.15%"],
                }
            )
        return pd.DataFrame(
            {
                "持有期限": ["小于7天"],
                "赎回费率": ["1.50%"],
            }
        )

    def rating_fetcher():
        calls.append(("rating", None))
        return pd.DataFrame({"代码": ["017763"], "晨星评级": ["5"]})

    result = fetch_fund_info(
        "017763",
        basic_fetcher=basic_fetcher,
        purchase_fetcher=purchase_fetcher,
        fee_fetcher=fee_fetcher,
        rating_fetcher=rating_fetcher,
        clock=lambda: "2026-06-07T12:00:00+00:00",
    )

    assert result.name == "银河领先债券C"
    assert result.purchase_status == "开放申购"
    assert result.morningstar_rating == "5"
    assert result.purchase_fee[0]["max_amount"] == 1000000
    assert result.redemption_fee[0]["max_holding_days"] == 7
    assert calls == [
        ("basic", "017763"),
        ("purchase_status", None),
        ("fee", "017763", "申购费率（前端）"),
        ("fee", "017763", "赎回费率"),
        ("rating", None),
    ]
```

- [ ] **Step 2: Run the aggregation test and verify it fails**

Run:

```bash
pytest tests/test_sources.py::test_fetch_fund_info_aggregates_akshare_frames -v
```

Expected: FAIL because `fetch_fund_info` does not accept injected fetchers.

- [ ] **Step 3: Implement `fetch_fund_info`**

In `src/finance_cli/sources.py`, add:

```python
def fetch_fund_info(
    code: str,
    basic_fetcher: Callable[..., pd.DataFrame] | None = None,
    purchase_fetcher: Callable[..., pd.DataFrame] | None = None,
    fee_fetcher: Callable[..., pd.DataFrame] | None = None,
    rating_fetcher: Callable[..., pd.DataFrame] | None = None,
    clock: Callable[[], str] | None = None,
) -> FundInfo:
    normalized_code = normalize_fund_code(code)
    if basic_fetcher is None or purchase_fetcher is None or fee_fetcher is None or rating_fetcher is None:
        try:
            import akshare as ak
        except Exception as exc:
            raise DataSourceError(f"Failed to import akshare: {exc}") from exc
        basic_fetcher = basic_fetcher or ak.fund_individual_basic_info_xq
        purchase_fetcher = purchase_fetcher or ak.fund_purchase_em
        fee_fetcher = fee_fetcher or ak.fund_fee_em
        rating_fetcher = rating_fetcher or ak.fund_rating_all

    now = clock or (lambda: datetime.now(timezone.utc).isoformat())
    try:
        basic_frame = basic_fetcher(symbol=normalized_code)
    except TypeError:
        basic_frame = basic_fetcher(normalized_code)
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch fund basic info for {normalized_code}: {exc}") from exc

    try:
        purchase_status_frame = purchase_fetcher()
    except Exception:
        purchase_status_frame = pd.DataFrame()

    try:
        purchase_fee_frame = fee_fetcher(symbol=normalized_code, indicator="申购费率（前端）")
    except Exception:
        purchase_fee_frame = pd.DataFrame()

    try:
        redemption_fee_frame = fee_fetcher(symbol=normalized_code, indicator="赎回费率")
    except Exception:
        redemption_fee_frame = pd.DataFrame()

    try:
        rating_frame = rating_fetcher()
    except Exception:
        rating_frame = pd.DataFrame()

    return normalize_fund_info(
        normalized_code,
        basic_frame,
        purchase_status_frame,
        purchase_fee_frame,
        redemption_fee_frame,
        rating_frame,
        updated_at=now(),
    )
```

Confirm `datetime` and `timezone` are already imported at the top of `sources.py`; they are currently imported for existing functions. Use the existing imports.

- [ ] **Step 4: Run source tests and verify they pass**

Run:

```bash
pytest tests/test_sources.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit fetch aggregation**

Run:

```bash
git add src/finance_cli/sources.py tests/test_sources.py
git commit -m "feat: fetch fund info from akshare"
```

Expected: commit succeeds.

---

### Task 6: CLI Commands And Manual JSON Validation

**Files:**
- Modify: `src/finance_cli/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add `FundInfo` to the import in `tests/test_cli.py`:

```python
from finance_cli.db import DailyMetric, FundInfo, SQLiteApiError
```

Add this helper in `tests/test_cli.py`:

```python
def _fund_info_payload():
    return {
        "code": "017763",
        "name": "银河领先债券C",
        "fund_type": "债券型",
        "established_date": "2023-01-01",
        "asset_size": "10.25亿元",
        "purchase_status": "开放申购",
        "redemption_status": "开放赎回",
        "morningstar_rating": "5",
        "purchase_fee": [
            {
                "min_amount": 0,
                "max_amount": 1000000,
                "original_rate": 0.015,
                "discounted_rate": 0.0015,
            }
        ],
        "redemption_fee": [
            {
                "min_holding_days": 0,
                "max_holding_days": 7,
                "original_rate": 0.015,
                "discounted_rate": 0.015,
            }
        ],
        "source": "manual",
        "updated_at": "2026-06-07T12:00:00+00:00",
    }
```

Add these tests:

```python
def test_fund_info_command_outputs_cached_json(monkeypatch):
    seen = {}

    def query_fund_info(self, code, fetch_missing, refresh=False):
        seen["code"] = code
        seen["refresh"] = refresh
        return FundInfo(**_fund_info_payload())

    monkeypatch.setattr("finance_cli.service.MetricsService.query_fund_info", query_fund_info)

    result = runner.invoke(app, ["fund-info", "--code", "017763", "--json"])

    assert result.exit_code == 0
    assert seen == {"code": "017763", "refresh": False}
    payload = json.loads(result.output)
    assert payload["code"] == "017763"
    assert payload["name"] == "银河领先债券C"
    assert payload["purchase_fee"][0]["discounted_rate"] == 0.0015


def test_fund_info_command_passes_refresh(monkeypatch):
    seen = {}

    def query_fund_info(self, code, fetch_missing, refresh=False):
        seen["refresh"] = refresh
        return FundInfo(**_fund_info_payload())

    monkeypatch.setattr("finance_cli.service.MetricsService.query_fund_info", query_fund_info)

    result = runner.invoke(app, ["fund-info", "--code", "017763", "--refresh"])

    assert result.exit_code == 0
    assert seen["refresh"] is True
    assert "基金名称: 银河领先债券C" in result.output


def test_fund_info_update_accepts_inline_json(monkeypatch):
    seen = {}

    def update_fund_info(self, fund_info):
        seen["fund_info"] = fund_info
        return fund_info

    monkeypatch.setattr("finance_cli.service.MetricsService.update_fund_info", update_fund_info)

    result = runner.invoke(
        app,
        [
            "fund-info-update",
            "--code",
            "017763",
            "--data",
            json.dumps(_fund_info_payload(), ensure_ascii=False),
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert seen["fund_info"].code == "017763"
    assert seen["fund_info"].source == "manual"
    payload = json.loads(result.output)
    assert payload["name"] == "银河领先债券C"


def test_fund_info_update_accepts_json_file(monkeypatch, tmp_path):
    seen = {}

    def update_fund_info(self, fund_info):
        seen["fund_info"] = fund_info
        return fund_info

    data_file = tmp_path / "fund-info.json"
    data_file.write_text(json.dumps(_fund_info_payload(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("finance_cli.service.MetricsService.update_fund_info", update_fund_info)

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data-file", str(data_file), "--json"],
    )

    assert result.exit_code == 0
    assert seen["fund_info"].code == "017763"


def test_fund_info_update_rejects_data_and_data_file_conflict(tmp_path):
    data_file = tmp_path / "fund-info.json"
    data_file.write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "fund-info-update",
            "--code",
            "017763",
            "--data",
            "{}",
            "--data-file",
            str(data_file),
            "--json",
        ],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "invalid_parameter"
    assert "--data and --data-file cannot be used together" in payload["error"]["message"]


def test_fund_info_update_rejects_unknown_field():
    payload = _fund_info_payload()
    payload["unexpected"] = "bad"

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "Unknown fund info fields" in error["message"]


def test_fund_info_update_rejects_code_mismatch():
    payload = _fund_info_payload()
    payload["code"] = "000001"

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "JSON code must match --code" in error["message"]


def test_fund_info_update_rejects_missing_data_inputs():
    result = runner.invoke(app, ["fund-info-update", "--code", "017763", "--json"])

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "one of --data or --data-file is required" in error["message"]


def test_fund_info_update_rejects_invalid_json():
    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", "{bad", "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "invalid JSON" in error["message"]


def test_fund_info_update_rejects_invalid_fee_tier_shape():
    payload = _fund_info_payload()
    payload["purchase_fee"] = [
        {
            "min_amount": "zero",
            "max_amount": 1000000,
            "original_rate": 0.015,
            "discounted_rate": 0.0015,
        }
    ]

    result = runner.invoke(
        app,
        ["fund-info-update", "--code", "017763", "--data", json.dumps(payload), "--json"],
    )

    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["code"] == "invalid_parameter"
    assert "purchase_fee min_amount must be a number" in error["message"]
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because `fund-info` and `fund-info-update` commands do not exist.

- [ ] **Step 3: Implement CLI commands and validation**

In `src/finance_cli/cli.py`, update imports:

```python
from finance_cli.db import FundInfo, MetricsRepository, SQLiteApiError
from finance_cli.output import (
    format_fund_info_json,
    format_fund_info_text,
    format_json,
    format_range_json,
    format_range_text,
    format_text,
)
from finance_cli.sources import (
    DataSourceError,
    compute_dividend_yield_spread_rows,
    compute_gold_m2_ratio_rows,
    fetch_cn10y_yield_rows,
    fetch_dividend_yield_spread_rows,
    fetch_fund_info,
    fetch_fund_nav_rows,
    fetch_gold_rows,
    fetch_gold_m2_ratio_rows,
    fetch_gold_usd_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_pb_rows,
    fetch_index_pe_rows,
    fetch_m2_rows,
    normalize_fund_code,
    normalize_index_pe_code,
    normalize_csindex_code,
    fetch_sw_index_pb_rows,
)
```

Add these constants and helpers near the existing helper functions:

```python
FUND_INFO_FIELDS = {
    "code",
    "name",
    "fund_type",
    "established_date",
    "asset_size",
    "purchase_status",
    "redemption_status",
    "morningstar_rating",
    "purchase_fee",
    "redemption_fee",
    "source",
    "updated_at",
}
PURCHASE_FEE_FIELDS = {
    "min_amount",
    "max_amount",
    "original_rate",
    "discounted_rate",
    "fixed_fee",
}
REDEMPTION_FEE_FIELDS = {
    "min_holding_days",
    "max_holding_days",
    "original_rate",
    "discounted_rate",
    "fixed_fee",
}


def _load_fund_info_payload(data: str | None, data_file: str | None) -> dict[str, object]:
    if data is not None and data_file is not None:
        raise JsonClickException(
            "invalid_parameter",
            "--data and --data-file cannot be used together",
            exit_code=2,
        )
    if data is None and data_file is None:
        raise JsonClickException(
            "invalid_parameter",
            "one of --data or --data-file is required",
            exit_code=2,
        )
    try:
        raw = data if data is not None else Path(data_file).read_text(encoding="utf-8")
        payload = json.loads(raw)
    except OSError as exc:
        raise JsonClickException("invalid_parameter", f"failed to read --data-file: {exc}", exit_code=2) from exc
    except json.JSONDecodeError as exc:
        raise JsonClickException("invalid_parameter", f"invalid JSON: {exc.msg}", exit_code=2) from exc
    if not isinstance(payload, dict):
        raise JsonClickException("invalid_parameter", "fund info JSON must be an object", exit_code=2)
    return payload


def _fund_info_from_payload(code: str, payload: dict[str, object]) -> FundInfo:
    unknown_fields = set(payload) - FUND_INFO_FIELDS
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise JsonClickException("invalid_parameter", f"Unknown fund info fields: {names}", exit_code=2)
    payload_code = payload.get("code")
    if payload_code is not None and str(payload_code) != code:
        raise JsonClickException("invalid_parameter", "JSON code must match --code", exit_code=2)
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise JsonClickException("invalid_parameter", "name is required", exit_code=2)
    source = payload.get("source", "manual")
    if not isinstance(source, str) or not source.strip():
        raise JsonClickException("invalid_parameter", "source must be a non-empty string", exit_code=2)
    updated_at = payload.get("updated_at") or datetime.now(UTC).isoformat()
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise JsonClickException("invalid_parameter", "updated_at must be a string", exit_code=2)
    purchase_fee = _validate_fee_list(payload.get("purchase_fee", []), PURCHASE_FEE_FIELDS, "purchase_fee")
    redemption_fee = _validate_fee_list(payload.get("redemption_fee", []), REDEMPTION_FEE_FIELDS, "redemption_fee")
    return FundInfo(
        code=code,
        name=name.strip(),
        fund_type=_optional_payload_str(payload.get("fund_type")),
        established_date=_optional_payload_str(payload.get("established_date")),
        asset_size=_optional_payload_str(payload.get("asset_size")),
        purchase_status=_optional_payload_str(payload.get("purchase_status")),
        redemption_status=_optional_payload_str(payload.get("redemption_status")),
        morningstar_rating=_optional_payload_str(payload.get("morningstar_rating")),
        purchase_fee=purchase_fee,
        redemption_fee=redemption_fee,
        source=source.strip(),
        updated_at=updated_at.strip(),
    )


def _validate_fee_list(value: object, allowed_fields: set[str], field_name: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise JsonClickException("invalid_parameter", f"{field_name} must be a list", exit_code=2)
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise JsonClickException("invalid_parameter", f"{field_name} items must be objects", exit_code=2)
        unknown_fields = set(item) - allowed_fields
        if unknown_fields:
            names = ", ".join(sorted(unknown_fields))
            raise JsonClickException("invalid_parameter", f"Unknown {field_name} fields: {names}", exit_code=2)
        tier = dict(item)
        if field_name == "purchase_fee":
            _validate_purchase_fee_tier(tier)
        else:
            _validate_redemption_fee_tier(tier)
        result.append(tier)
    return result


def _validate_purchase_fee_tier(tier: dict[str, object]) -> None:
    _require_number(tier, "min_amount", "purchase_fee")
    _require_optional_number(tier, "max_amount", "purchase_fee")
    _require_optional_number(tier, "original_rate", "purchase_fee")
    _require_optional_number(tier, "discounted_rate", "purchase_fee")
    if "fixed_fee" in tier:
        _require_optional_number(tier, "fixed_fee", "purchase_fee")


def _validate_redemption_fee_tier(tier: dict[str, object]) -> None:
    _require_number(tier, "min_holding_days", "redemption_fee")
    _require_optional_number(tier, "max_holding_days", "redemption_fee")
    _require_optional_number(tier, "original_rate", "redemption_fee")
    _require_optional_number(tier, "discounted_rate", "redemption_fee")
    if "fixed_fee" in tier:
        _require_optional_number(tier, "fixed_fee", "redemption_fee")


def _require_number(tier: dict[str, object], field: str, fee_name: str) -> None:
    value = tier.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise JsonClickException("invalid_parameter", f"{fee_name} {field} must be a number", exit_code=2)


def _require_optional_number(tier: dict[str, object], field: str, fee_name: str) -> None:
    value = tier.get(field)
    if value is not None and (not isinstance(value, int | float) or isinstance(value, bool)):
        raise JsonClickException("invalid_parameter", f"{fee_name} {field} must be a number or null", exit_code=2)


def _optional_payload_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise JsonClickException("invalid_parameter", "optional fund info fields must be strings or null", exit_code=2)
    return value
```

Add imports near the top:

```python
from datetime import UTC, date, datetime
from pathlib import Path
```

Replace the existing `from datetime import date` import with the combined import.

Add commands before `fund_nav`:

```python
@app.command("fund-info")
def fund_info(
    code: str = typer.Option(..., "--code"),
    refresh: bool = typer.Option(False, "--refresh"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query fund profile, fees, purchase status, and rating."""
    try:
        normalized_code = normalize_fund_code(code)
        result = _service().query_fund_info(
            normalized_code,
            lambda: fetch_fund_info(normalized_code),
            refresh=refresh,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_fund_info_json(result) if json_output else format_fund_info_text(result))


@app.command("fund-info-update")
def fund_info_update(
    code: str = typer.Option(..., "--code"),
    data: str | None = typer.Option(None, "--data"),
    data_file: str | None = typer.Option(None, "--data-file"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Manually update fund profile data from JSON."""
    try:
        normalized_code = normalize_fund_code(code)
        payload = _load_fund_info_payload(data, data_file)
        fund_info = _fund_info_from_payload(normalized_code, payload)
        result = _service().update_fund_info(fund_info)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except JsonClickException:
        raise
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_fund_info_json(result) if json_output else format_fund_info_text(result))
```

- [ ] **Step 4: Run focused CLI tests and verify they pass**

Run:

```bash
pytest tests/test_cli.py::test_fund_info_command_outputs_cached_json tests/test_cli.py::test_fund_info_command_passes_refresh tests/test_cli.py::test_fund_info_update_accepts_inline_json tests/test_cli.py::test_fund_info_update_accepts_json_file tests/test_cli.py::test_fund_info_update_rejects_data_and_data_file_conflict tests/test_cli.py::test_fund_info_update_rejects_unknown_field tests/test_cli.py::test_fund_info_update_rejects_code_mismatch tests/test_cli.py::test_fund_info_update_rejects_missing_data_inputs tests/test_cli.py::test_fund_info_update_rejects_invalid_json tests/test_cli.py::test_fund_info_update_rejects_invalid_fee_tier_shape -v
```

Expected: PASS.

- [ ] **Step 5: Run all CLI tests and verify they pass**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit CLI layer**

Run:

```bash
git add src/finance_cli/cli.py tests/test_cli.py
git commit -m "feat: add fund info cli commands"
```

Expected: commit succeeds.

---

### Task 7: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README command documentation**

Add this section after the existing fund NAV section in `README.md`:

````markdown
Query fund profile data, fees, purchase status, and Morningstar rating:

```bash
finance fund-info --code 017763
finance fund-info --code 017763 --refresh --json
```

`fund-info` does not fetch fund NAV. By default it reads the remote SQLite database first.
If no cached row exists, it fetches fund profile data from akshare, stores it in `fund_info`,
and returns the saved row. `--refresh` forces a fresh akshare fetch and overwrites the
stored row.

Manually update fund profile data:

```bash
finance fund-info-update --code 017763 --data '{"name":"银河领先债券C","purchase_fee":[],"redemption_fee":[],"source":"manual"}'
finance fund-info-update --code 017763 --data-file ./fund-info.json
```

Manual update JSON uses the same shape as `finance fund-info --json`.
`purchase_fee` is an array of purchase amount tiers. Amounts are in yuan, and rates use
decimal values where `0.015` means `1.5%`.

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
  "purchase_fee": [
    {
      "min_amount": 0,
      "max_amount": 1000000,
      "original_rate": 0.015,
      "discounted_rate": 0.0015
    }
  ],
  "redemption_fee": [
    {
      "min_holding_days": 0,
      "max_holding_days": 7,
      "original_rate": 0.015,
      "discounted_rate": 0.015
    }
  ],
  "source": "manual",
  "updated_at": "2026-06-07T12:00:00+00:00"
}
```
````

Also add `finance fund-info --code 017763 --json` to the existing JSON command examples.

- [ ] **Step 2: Run README-related CLI help check**

Run:

```bash
python -m finance_cli --help
```

Expected output includes `fund-info` and `fund-info-update`.

- [ ] **Step 3: Run full test suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 4: Commit documentation**

Run:

```bash
git add README.md
git commit -m "docs: document fund info commands"
```

Expected: commit succeeds.

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short
```

Expected: only unrelated pre-existing user changes remain, or the working tree is clean if those changes were part of the implementation branch. Do not revert unrelated user changes.

---

## Self-Review

- Spec coverage: Tasks cover the dedicated `fund_info` table, fixed fields, JSON fee arrays, cache-first query, forced refresh, manual JSON update from inline data and file, akshare aggregation, validation errors, output, tests, and README documentation.
- Scope check: The plan does not add batch sync, NAV changes, SQL-queryable fee tables, screening, or raw payload storage.
- Type consistency: `FundInfo` fields match the spec and are used consistently across repository, service, output, CLI, and tests.
- Worktree safety: Each commit step stages only files touched by that task. Existing unrelated uncommitted changes must not be reverted.
