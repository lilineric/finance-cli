# Index PE and Gold CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python `finance` CLI that queries index PE-TTM and Shanghai Gold Exchange Au9999 close-price historical percentiles, backed by SQLite and akshare.

**Architecture:** Use a small Typer CLI over focused modules: configuration, SQLite repository, source adapters, percentile calculation, query service, and output formatting. Query commands and manual sync commands share the same source and repository logic so behavior stays consistent.

**Tech Stack:** Python 3.11+, Typer, SQLite from the standard library, pandas, akshare, pytest.

---

## File Structure

- Create `pyproject.toml`: package metadata, console script, dependencies, pytest config.
- Create `src/finance_cli/__init__.py`: package version.
- Create `src/finance_cli/__main__.py`: `python -m finance_cli` entrypoint.
- Create `src/finance_cli/cli.py`: Typer app, commands, validation, output selection.
- Create `src/finance_cli/config.py`: database path resolution.
- Create `src/finance_cli/db.py`: SQLite schema, upsert, latest-date lookup, range query.
- Create `src/finance_cli/sources.py`: akshare adapters and normalized daily metric rows.
- Create `src/finance_cli/analytics.py`: date parsing, lookback calculation, percentile calculation.
- Create `src/finance_cli/service.py`: orchestration for sync and query.
- Create `src/finance_cli/output.py`: text and JSON output.
- Create `tests/test_analytics.py`: pure percentile/date tests.
- Create `tests/test_db.py`: SQLite repository tests.
- Create `tests/test_sources.py`: mocked akshare normalization tests.
- Create `tests/test_cli.py`: CLI behavior tests with mocked service calls.
- Modify `README.md`: add install and command examples.

---

### Task 1: Project Scaffold and Empty CLI

**Files:**
- Create: `pyproject.toml`
- Create: `src/finance_cli/__init__.py`
- Create: `src/finance_cli/__main__.py`
- Create: `src/finance_cli/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI scaffold test**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from finance_cli.cli import app


runner = CliRunner()


def test_cli_help_shows_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pe" in result.output
    assert "gold" in result.output
    assert "sync" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_cli.py::test_cli_help_shows_commands -v
```

Expected: FAIL because `finance_cli` does not exist.

- [ ] **Step 3: Add package scaffold**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "finance-cli"
version = "0.1.0"
description = "Financial data CLI backed by SQLite and akshare"
requires-python = ">=3.11"
dependencies = [
  "akshare>=1.16.0",
  "pandas>=2.0.0",
  "typer>=0.12.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
]

[project.scripts]
finance = "finance_cli.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `src/finance_cli/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/finance_cli/__main__.py`:

```python
from .cli import app


if __name__ == "__main__":
    app()
```

Create `src/finance_cli/cli.py`:

```python
import typer


app = typer.Typer(help="Financial data CLI")
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")


@app.command()
def pe() -> None:
    """Query index PE-TTM percentile."""
    typer.echo("PE query is not implemented yet.")


@app.command()
def gold() -> None:
    """Query Au9999 gold close-price percentile."""
    typer.echo("Gold query is not implemented yet.")


@sync_app.command("pe")
def sync_pe() -> None:
    """Synchronize index PE-TTM history."""
    typer.echo("PE sync is not implemented yet.")


@sync_app.command("gold")
def sync_gold() -> None:
    """Synchronize Au9999 gold price history."""
    typer.echo("Gold sync is not implemented yet.")
```

- [ ] **Step 4: Run scaffold test**

Run:

```bash
pytest tests/test_cli.py::test_cli_help_shows_commands -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/finance_cli tests/test_cli.py
git commit -m "feat: scaffold finance cli"
```

---

### Task 2: Analytics Logic

**Files:**
- Create: `src/finance_cli/analytics.py`
- Create: `tests/test_analytics.py`

- [ ] **Step 1: Write failing analytics tests**

Create `tests/test_analytics.py`:

```python
from datetime import date

import pytest

from finance_cli.analytics import (
    calculate_percentile,
    parse_query_date,
    start_date_for_years,
    validate_years,
)


def test_calculate_percentile_uses_less_than_or_equal_formula():
    result = calculate_percentile([10.0, 20.0, 30.0], 20.0)

    assert result == pytest.approx(66.6666667)


def test_calculate_percentile_historical_max_is_100():
    result = calculate_percentile([10.0, 20.0, 30.0], 30.0)

    assert result == 100.0


def test_calculate_percentile_rejects_empty_values():
    with pytest.raises(ValueError, match="No values available"):
        calculate_percentile([], 30.0)


def test_parse_query_date_accepts_iso_date():
    assert parse_query_date("2026-04-20") == date(2026, 4, 20)


def test_parse_query_date_rejects_invalid_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_query_date("2026/04/20")


def test_validate_years_accepts_1_to_10():
    assert validate_years(1) == 1
    assert validate_years(10) == 10


def test_validate_years_rejects_out_of_range_values():
    with pytest.raises(ValueError, match="between 1 and 10"):
        validate_years(0)
    with pytest.raises(ValueError, match="between 1 and 10"):
        validate_years(11)


def test_start_date_for_years_handles_leap_day():
    assert start_date_for_years(date(2024, 2, 29), 1) == date(2023, 2, 28)
```

- [ ] **Step 2: Run analytics tests to verify failure**

Run:

```bash
pytest tests/test_analytics.py -v
```

Expected: FAIL because `finance_cli.analytics` does not exist.

- [ ] **Step 3: Implement analytics module**

Create `src/finance_cli/analytics.py`:

```python
from datetime import date, datetime
from typing import Iterable


def parse_query_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format") from exc


def validate_years(years: int) -> int:
    if years < 1 or years > 10:
        raise ValueError("Years must be between 1 and 10")
    return years


def start_date_for_years(end_date: date, years: int) -> date:
    validate_years(years)
    try:
        return end_date.replace(year=end_date.year - years)
    except ValueError:
        return end_date.replace(year=end_date.year - years, day=28)


def calculate_percentile(values: Iterable[float], current_value: float) -> float:
    samples = list(values)
    if not samples:
        raise ValueError("No values available for percentile calculation")
    less_or_equal_count = sum(1 for value in samples if value <= current_value)
    return less_or_equal_count / len(samples) * 100
```

- [ ] **Step 4: Run analytics tests**

Run:

```bash
pytest tests/test_analytics.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/finance_cli/analytics.py tests/test_analytics.py
git commit -m "feat: add percentile analytics"
```

---

### Task 3: SQLite Repository

**Files:**
- Create: `src/finance_cli/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_db.py`:

```python
from finance_cli.db import DailyMetric, MetricsRepository


def test_repository_upserts_and_queries_latest_date(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "pe_ttm", "2026-04-17", 12.3, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 12.8, "test"),
        ]
    )

    assert repo.latest_date_on_or_before("index", "000300", "pe_ttm", "2026-04-19") == "2026-04-17"


def test_repository_range_query_excludes_future_rows(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    repo.upsert_metrics(
        [
            DailyMetric("gold", "AU9999", "close", "2026-04-18", 530.0, "test"),
            DailyMetric("gold", "AU9999", "close", "2026-04-20", 540.0, "test"),
            DailyMetric("gold", "AU9999", "close", "2026-04-21", 550.0, "test"),
        ]
    )

    rows = repo.metrics_between("gold", "AU9999", "close", "2026-04-01", "2026-04-20")

    assert [row.date for row in rows] == ["2026-04-18", "2026-04-20"]
    assert [row.value for row in rows] == [530.0, 540.0]


def test_repository_upsert_replaces_existing_value(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    repo.initialize()

    repo.upsert_metrics([DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 12.8, "first")])
    repo.upsert_metrics([DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 13.1, "second")])

    rows = repo.metrics_between("index", "000300", "pe_ttm", "2026-04-20", "2026-04-20")

    assert len(rows) == 1
    assert rows[0].value == 13.1
    assert rows[0].source == "second"
```

- [ ] **Step 2: Run repository tests to verify failure**

Run:

```bash
pytest tests/test_db.py -v
```

Expected: FAIL because `finance_cli.db` does not exist.

- [ ] **Step 3: Implement SQLite repository**

Create `src/finance_cli/db.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class DailyMetric:
    asset_type: str
    code: str
    metric: str
    date: str
    value: float
    source: str


class MetricsRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_metrics (
                  asset_type TEXT NOT NULL,
                  code TEXT NOT NULL,
                  metric TEXT NOT NULL,
                  date TEXT NOT NULL,
                  value REAL NOT NULL,
                  source TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (asset_type, code, metric, date)
                )
                """
            )

    def upsert_metrics(self, metrics: list[DailyMetric]) -> int:
        if not metrics:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_metrics (
                  asset_type, code, metric, date, value, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_type, code, metric, date) DO UPDATE SET
                  value = excluded.value,
                  source = excluded.source,
                  updated_at = excluded.updated_at
                """,
                [
                    (
                        row.asset_type,
                        row.code,
                        row.metric,
                        row.date,
                        row.value,
                        row.source,
                        now,
                    )
                    for row in metrics
                ],
            )
        return len(metrics)

    def latest_date_on_or_before(
        self, asset_type: str, code: str, metric: str, end_date: str
    ) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT date
                FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                  AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                (asset_type, code, metric, end_date),
            ).fetchone()
        return None if row is None else str(row["date"])

    def metrics_between(
        self, asset_type: str, code: str, metric: str, start_date: str, end_date: str
    ) -> list[DailyMetric]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT asset_type, code, metric, date, value, source
                FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                  AND date >= ?
                  AND date <= ?
                ORDER BY date
                """,
                (asset_type, code, metric, start_date, end_date),
            ).fetchall()
        return [
            DailyMetric(
                asset_type=str(row["asset_type"]),
                code=str(row["code"]),
                metric=str(row["metric"]),
                date=str(row["date"]),
                value=float(row["value"]),
                source=str(row["source"]),
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
```

- [ ] **Step 4: Run repository tests**

Run:

```bash
pytest tests/test_db.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/finance_cli/db.py tests/test_db.py
git commit -m "feat: add sqlite metrics repository"
```

---

### Task 4: akshare Source Adapters

**Files:**
- Create: `src/finance_cli/sources.py`
- Create: `tests/test_sources.py`

- [ ] **Step 1: Write failing source normalization tests**

Create `tests/test_sources.py`:

```python
import pandas as pd

from finance_cli.sources import normalize_gold_rows, normalize_index_pe_rows


def test_normalize_index_pe_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "滚动市盈率": [12.3, 12.8],
        }
    )

    rows = normalize_index_pe_rows("000300", frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value) for row in rows] == [
        ("index", "000300", "pe_ttm", "2026-04-17", 12.3),
        ("index", "000300", "pe_ttm", "2026-04-20", 12.8),
    ]


def test_normalize_gold_rows_accepts_common_akshare_columns():
    frame = pd.DataFrame(
        {
            "日期": ["2026-04-17", "2026-04-20"],
            "收盘价": [530.5, 535.2],
        }
    )

    rows = normalize_gold_rows(frame)

    assert [(row.asset_type, row.code, row.metric, row.date, row.value) for row in rows] == [
        ("gold", "AU9999", "close", "2026-04-17", 530.5),
        ("gold", "AU9999", "close", "2026-04-20", 535.2),
    ]
```

- [ ] **Step 2: Run source tests to verify failure**

Run:

```bash
pytest tests/test_sources.py -v
```

Expected: FAIL because `finance_cli.sources` does not exist.

- [ ] **Step 3: Implement source normalization and fetch wrappers**

Create `src/finance_cli/sources.py`:

```python
from collections.abc import Callable
from datetime import date

import pandas as pd

from .db import DailyMetric


INDEX_PE_DATE_COLUMNS = ("日期", "date", "trade_date")
INDEX_PE_VALUE_COLUMNS = ("滚动市盈率", "市盈率TTM", "pe_ttm", "PE_TTM")
GOLD_DATE_COLUMNS = ("日期", "date", "trade_date")
GOLD_CLOSE_COLUMNS = ("收盘价", "close", "收盘")


class DataSourceError(RuntimeError):
    pass


def fetch_index_pe_rows(code: str, fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    if fetcher is None:
        import akshare as ak

        fetcher = ak.stock_zh_index_value_csindex
    try:
        frame = fetcher(symbol=code)
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch index PE data for {code}: {exc}") from exc
    return normalize_index_pe_rows(code, frame)


def fetch_gold_rows(fetcher: Callable[..., pd.DataFrame] | None = None) -> list[DailyMetric]:
    if fetcher is None:
        import akshare as ak

        fetcher = ak.spot_hist_sge
    try:
        frame = fetcher(symbol="Au99.99")
    except Exception as exc:
        raise DataSourceError(f"Failed to fetch Au9999 gold data: {exc}") from exc
    return normalize_gold_rows(frame)


def normalize_index_pe_rows(code: str, frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, INDEX_PE_DATE_COLUMNS)
    value_column = _first_existing_column(frame, INDEX_PE_VALUE_COLUMNS)
    rows: list[DailyMetric] = []
    for _, raw in frame.iterrows():
        metric_date = _to_iso_date(raw[date_column])
        value = _to_float(raw[value_column])
        rows.append(DailyMetric("index", code, "pe_ttm", metric_date, value, "akshare"))
    return rows


def normalize_gold_rows(frame: pd.DataFrame) -> list[DailyMetric]:
    date_column = _first_existing_column(frame, GOLD_DATE_COLUMNS)
    value_column = _first_existing_column(frame, GOLD_CLOSE_COLUMNS)
    rows: list[DailyMetric] = []
    for _, raw in frame.iterrows():
        metric_date = _to_iso_date(raw[date_column])
        value = _to_float(raw[value_column])
        rows.append(DailyMetric("gold", "AU9999", "close", metric_date, value, "akshare"))
    return rows


def _first_existing_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in frame.columns:
            return column
    raise DataSourceError(f"Missing expected column; tried {', '.join(candidates)}")


def _to_iso_date(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return pd.to_datetime(value).date().isoformat()


def _to_float(value: object) -> float:
    numeric = pd.to_numeric(value)
    if pd.isna(numeric):
        raise DataSourceError("Metric value is not numeric")
    return float(numeric)
```

- [ ] **Step 4: Run source tests**

Run:

```bash
pytest tests/test_sources.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/finance_cli/sources.py tests/test_sources.py
git commit -m "feat: add akshare source adapters"
```

---

### Task 5: Query and Sync Service

**Files:**
- Create: `src/finance_cli/service.py`
- Modify: `tests/test_analytics.py`
- Create: `tests/test_service.py`

- [ ] **Step 1: Add service tests**

Create `tests/test_service.py`:

```python
from finance_cli.db import DailyMetric, MetricsRepository
from finance_cli.service import MetricQueryResult, MetricsService


def test_query_falls_back_to_previous_available_date_and_excludes_future_rows(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "pe_ttm", "2026-04-17", 10.0, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-20", 20.0, "test"),
            DailyMetric("index", "000300", "pe_ttm", "2026-04-21", 30.0, "test"),
        ]
    )

    result = service.query(
        asset_type="index",
        code="000300",
        metric="pe_ttm",
        requested_date="2026-04-19",
        years=1,
        fetch_missing=lambda: [],
    )

    assert result == MetricQueryResult(
        asset_type="index",
        code="000300",
        metric="pe_ttm",
        requested_date="2026-04-19",
        actual_date="2026-04-17",
        value=10.0,
        percentile=100.0,
        sample_count=1,
        source="test",
    )


def test_query_fetches_missing_data_before_calculating(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)

    result = service.query(
        asset_type="gold",
        code="AU9999",
        metric="close",
        requested_date="2026-04-20",
        years=1,
        fetch_missing=lambda: [
            DailyMetric("gold", "AU9999", "close", "2026-04-17", 530.0, "test"),
            DailyMetric("gold", "AU9999", "close", "2026-04-20", 540.0, "test"),
        ],
    )

    assert result.actual_date == "2026-04-20"
    assert result.value == 540.0
    assert result.percentile == 100.0
    assert result.sample_count == 2


def test_query_raises_when_no_data_exists_after_fetch(tmp_path):
    repo = MetricsRepository(tmp_path / "finance.db")
    service = MetricsService(repo)

    try:
        service.query(
            asset_type="index",
            code="000300",
            metric="pe_ttm",
            requested_date="2026-04-20",
            years=1,
            fetch_missing=lambda: [],
        )
    except ValueError as exc:
        assert "No data available" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
```

- [ ] **Step 2: Run service tests to verify failure**

Run:

```bash
pytest tests/test_service.py -v
```

Expected: FAIL because `finance_cli.service` does not exist.

- [ ] **Step 3: Implement service**

Create `src/finance_cli/service.py`:

```python
from collections.abc import Callable
from dataclasses import dataclass

from .analytics import calculate_percentile, parse_query_date, start_date_for_years, validate_years
from .db import DailyMetric, MetricsRepository


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

    def sync(self, fetch_rows: Callable[[], list[DailyMetric]]) -> int:
        self.repository.initialize()
        rows = fetch_rows()
        return self.repository.upsert_metrics(rows)

    def query(
        self,
        asset_type: str,
        code: str,
        metric: str,
        requested_date: str,
        years: int,
        fetch_missing: Callable[[], list[DailyMetric]],
    ) -> MetricQueryResult:
        query_date = parse_query_date(requested_date)
        validate_years(years)
        self.repository.initialize()

        actual_date = self.repository.latest_date_on_or_before(
            asset_type, code, metric, query_date.isoformat()
        )
        if actual_date is None:
            self.repository.upsert_metrics(fetch_missing())
            actual_date = self.repository.latest_date_on_or_before(
                asset_type, code, metric, query_date.isoformat()
            )
        if actual_date is None:
            raise ValueError(f"No data available for {asset_type}/{code}/{metric} on or before {requested_date}")

        start_date = start_date_for_years(parse_query_date(actual_date), years).isoformat()
        rows = self.repository.metrics_between(asset_type, code, metric, start_date, actual_date)
        if not rows:
            raise ValueError(f"No values available for {asset_type}/{code}/{metric} percentile calculation")

        current_row = rows[-1]
        percentile = calculate_percentile([row.value for row in rows], current_row.value)
        return MetricQueryResult(
            asset_type=asset_type,
            code=code,
            metric=metric,
            requested_date=requested_date,
            actual_date=actual_date,
            value=current_row.value,
            percentile=percentile,
            sample_count=len(rows),
            source=current_row.source,
        )
```

- [ ] **Step 4: Run service tests**

Run:

```bash
pytest tests/test_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Run analytics and db regression tests**

Run:

```bash
pytest tests/test_analytics.py tests/test_db.py tests/test_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/finance_cli/service.py tests/test_service.py
git commit -m "feat: add metrics query service"
```

---

### Task 6: Output Formatting and Config

**Files:**
- Create: `src/finance_cli/config.py`
- Create: `src/finance_cli/output.py`
- Create: `tests/test_output.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config and output tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

from finance_cli.config import default_db_path, resolve_db_path


def test_default_db_path_uses_home_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("FINANCE_CLI_DB", raising=False)

    assert default_db_path() == tmp_path / ".finance-cli" / "finance.db"


def test_resolve_db_path_uses_environment_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom.db"
    monkeypatch.setenv("FINANCE_CLI_DB", str(custom))

    assert resolve_db_path() == custom
```

Create `tests/test_output.py`:

```python
import json

from finance_cli.output import format_json, format_text
from finance_cli.service import MetricQueryResult


def test_format_json_uses_stable_keys():
    result = MetricQueryResult("index", "000300", "pe_ttm", "2026-04-20", "2026-04-17", 12.34, 42.8, 2000, "akshare")

    payload = json.loads(format_json(result))

    assert payload["asset_type"] == "index"
    assert payload["code"] == "000300"
    assert payload["metric"] == "pe_ttm"
    assert payload["requested_date"] == "2026-04-20"
    assert payload["actual_date"] == "2026-04-17"
    assert payload["value"] == 12.34
    assert payload["percentile"] == 42.8
    assert payload["sample_count"] == 2000
    assert payload["source"] == "akshare"


def test_format_text_includes_key_fields():
    result = MetricQueryResult("gold", "AU9999", "close", "2026-04-20", "2026-04-17", 535.2, 80.0, 2400, "akshare")

    text = format_text(result)

    assert "AU9999" in text
    assert "2026-04-20" in text
    assert "2026-04-17" in text
    assert "535.2" in text
    assert "80.0%" in text
    assert "2400" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_config.py tests/test_output.py -v
```

Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement config and output**

Create `src/finance_cli/config.py`:

```python
import os
from pathlib import Path


def default_db_path() -> Path:
    return Path.home() / ".finance-cli" / "finance.db"


def resolve_db_path() -> Path:
    override = os.environ.get("FINANCE_CLI_DB")
    if override:
        return Path(override).expanduser()
    return default_db_path()
```

Create `src/finance_cli/output.py`:

```python
import json

from .service import MetricQueryResult


def format_json(result: MetricQueryResult) -> str:
    return json.dumps(
        {
            "asset_type": result.asset_type,
            "code": result.code,
            "metric": result.metric,
            "requested_date": result.requested_date,
            "actual_date": result.actual_date,
            "value": result.value,
            "percentile": round(result.percentile, 1),
            "sample_count": result.sample_count,
            "source": result.source,
        },
        ensure_ascii=False,
    )


def format_text(result: MetricQueryResult) -> str:
    label = "指数" if result.asset_type == "index" else "黄金"
    value_label = "PE-TTM" if result.metric == "pe_ttm" else "收盘价"
    return "\n".join(
        [
            f"{label}: {result.code}",
            f"请求日期: {result.requested_date}",
            f"实际数据日期: {result.actual_date}",
            f"指标: {result.metric}",
            f"数据源: {result.source}",
            f"{value_label}: {result.value}",
            f"历史百分位: {round(result.percentile, 1)}%",
            f"样本数: {result.sample_count}",
        ]
    )
```

- [ ] **Step 4: Run config and output tests**

Run:

```bash
pytest tests/test_config.py tests/test_output.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/finance_cli/config.py src/finance_cli/output.py tests/test_config.py tests/test_output.py
git commit -m "feat: add cli config and output formatting"
```

---

### Task 7: Wire CLI Commands

**Files:**
- Modify: `src/finance_cli/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Replace CLI tests with command behavior tests**

Update `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from finance_cli.cli import app
from finance_cli.service import MetricQueryResult


runner = CliRunner()


def test_cli_help_shows_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pe" in result.output
    assert "gold" in result.output
    assert "sync" in result.output


def test_pe_command_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def fake_query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        return MetricQueryResult(asset_type, code, metric, requested_date, "2026-04-17", 12.3, 42.8, 2000, "akshare")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", fake_query)

    result = runner.invoke(app, ["pe", "--code", "000300", "--date", "2026-04-20", "--years", "10", "--json"])

    assert result.exit_code == 0
    assert '"code": "000300"' in result.output
    assert '"metric": "pe_ttm"' in result.output


def test_gold_command_outputs_text(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    def fake_query(self, asset_type, code, metric, requested_date, years, fetch_missing):
        return MetricQueryResult(asset_type, code, metric, requested_date, "2026-04-17", 535.2, 80.0, 2400, "akshare")

    monkeypatch.setattr("finance_cli.service.MetricsService.query", fake_query)

    result = runner.invoke(app, ["gold", "--date", "2026-04-20"])

    assert result.exit_code == 0
    assert "AU9999" in result.output
    assert "80.0%" in result.output


def test_sync_pe_outputs_inserted_count(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))
    monkeypatch.setattr("finance_cli.service.MetricsService.sync", lambda self, fetch_rows: 3)

    result = runner.invoke(app, ["sync", "pe", "--code", "000300"])

    assert result.exit_code == 0
    assert "同步 3 条记录" in result.output


def test_cli_reports_validation_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("FINANCE_CLI_DB", str(tmp_path / "finance.db"))

    result = runner.invoke(app, ["gold", "--years", "11"])

    assert result.exit_code != 0
    assert "between 1 and 10" in result.output
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because CLI has not been wired to the query service.

- [ ] **Step 3: Wire CLI to service, sources, config, and output**

Update `src/finance_cli/cli.py`:

```python
from datetime import date

import typer

from .analytics import validate_years
from .config import resolve_db_path
from .db import MetricsRepository
from .output import format_json, format_text
from .service import MetricsService
from .sources import fetch_gold_rows, fetch_index_pe_rows


app = typer.Typer(help="Financial data CLI")
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")


@app.command()
def pe(
    code: str = typer.Option(..., "--code", help="Index code, for example 000300"),
    query_date: str = typer.Option(default_factory=lambda: date.today().isoformat(), "--date", help="Query date in YYYY-MM-DD format"),
    years: int = typer.Option(10, "--years", help="Lookback years, 1 through 10"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Query index PE-TTM percentile."""
    try:
        validate_years(years)
        service = _service()
        result = service.query("index", code, "pe_ttm", query_date, years, lambda: fetch_index_pe_rows(code))
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(format_json(result) if as_json else format_text(result))


@app.command()
def gold(
    query_date: str = typer.Option(default_factory=lambda: date.today().isoformat(), "--date", help="Query date in YYYY-MM-DD format"),
    years: int = typer.Option(10, "--years", help="Lookback years, 1 through 10"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
) -> None:
    """Query Au9999 gold close-price percentile."""
    try:
        validate_years(years)
        service = _service()
        result = service.query("gold", "AU9999", "close", query_date, years, fetch_gold_rows)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(format_json(result) if as_json else format_text(result))


@sync_app.command("pe")
def sync_pe(
    code: str = typer.Option(..., "--code", help="Index code, for example 000300"),
) -> None:
    """Synchronize index PE-TTM history."""
    try:
        inserted = _service().sync(lambda: fetch_index_pe_rows(code))
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold")
def sync_gold() -> None:
    """Synchronize Au9999 gold price history."""
    try:
        inserted = _service().sync(fetch_gold_rows)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"同步 {inserted} 条记录")


def _service() -> MetricsService:
    return MetricsService(MetricsRepository(resolve_db_path()))
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/finance_cli/cli.py tests/test_cli.py
git commit -m "feat: wire pe and gold cli commands"
```

---

### Task 8: README and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with usage**

Update `README.md`:

```markdown
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

## Database

By default, data is stored at:

```text
~/.finance-cli/finance.db
```

Override the path with:

```bash
FINANCE_CLI_DB=/path/to/finance.db finance gold
```
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run local CLI help**

Run:

```bash
python -m finance_cli --help
python -m finance_cli pe --help
python -m finance_cli gold --help
python -m finance_cli sync --help
```

Expected: Each command exits 0 and shows the expected options.

- [ ] **Step 4: Commit README**

```bash
git add README.md
git commit -m "docs: add finance cli usage"
```

- [ ] **Step 5: Summarize implementation**

Run:

```bash
git status --short
git log --oneline --max-count=8
```

Expected: working tree is clean, and recent commits include the scaffold, analytics, repository, source adapters, service, CLI wiring, and README commits.

---

## Self-Review Notes

- Spec coverage: the plan covers one main `finance` command, `pe`, `gold`, `sync pe`, `sync gold`, SQLite storage, akshare adapters, non-future percentile calculation, text output, JSON output, and tests.
- Scope check: PE and gold share the same data model and service, so they remain one coherent implementation plan.
- Type consistency: shared metric rows use `DailyMetric`; query results use `MetricQueryResult`; date values stored in SQLite remain `YYYY-MM-DD` strings.
- Testing boundary: unit tests mock source behavior and do not require real network calls.
