# Range Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--from/--to` range mode to every existing finance CLI query command, returning raw values with actual data coverage dates and no percentile fields.

**Architecture:** Keep existing command names and add an early range branch in each query command. Add `MetricRangeQueryResult` and `MetricsService.query_range(...)` in the service layer, then add `format_range_json(...)` and `format_range_text(...)` in the output layer. Reuse `MetricsRepository.metrics_between(...)` and existing source fetchers.

**Tech Stack:** Python 3.11, Typer, pytest, dataclasses, existing SQLite API repository abstraction.

---

## File Structure

- Modify `src/finance_cli/service.py`: add range dataclasses and `MetricsService.query_range(...)`.
- Modify `src/finance_cli/output.py`: add JSON and text formatters for range results.
- Modify `src/finance_cli/cli.py`: add `--from/--to` options, range-mode validation, and range branches for all query commands.
- Modify `tests/test_service.py`: add service coverage for range behavior.
- Modify `tests/test_output.py`: add output coverage for range JSON/text fields.
- Modify `tests/test_cli.py`: add CLI coverage for each command and invalid range parameters.
- Modify `README.md`: document range query usage.

The working tree already has unrelated uncommitted changes in some of these files. Before each commit, inspect `git diff` and stage only hunks from this feature with `git add -p`.

---

### Task 1: Service Range Query

**Files:**
- Modify: `src/finance_cli/service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write failing service tests**

Append these tests to `tests/test_service.py`:

```python
def test_query_range_returns_rows_inside_requested_dates(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("index", "000300", "rolling_pe", "2025-12-31", 9.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-01-02", 10.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-01-05", 11.0, "test"),
            DailyMetric("index", "000300", "rolling_pe", "2026-05-02", 12.0, "test"),
        ]
    )

    result = service.query_range(
        asset_type="index",
        code="000300",
        metric="rolling_pe",
        requested_from="2026-01-01",
        requested_to="2026-05-01",
        fetch_missing=fail_fetch,
    )

    assert result.asset_type == "index"
    assert result.code == "000300"
    assert result.metric == "rolling_pe"
    assert result.requested_from == "2026-01-01"
    assert result.requested_to == "2026-05-01"
    assert result.actual_start_date == "2026-01-02"
    assert result.actual_end_date == "2026-01-05"
    assert result.data == [
        ("2026-01-02", 10.0, "test"),
        ("2026-01-05", 11.0, "test"),
    ]


def test_query_range_fetches_when_local_data_is_stale_for_end_date(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)
    repo.initialize()
    repo.upsert_metrics(
        [
            DailyMetric("gold", "AU9999", "close", "2026-01-02", 530.0, "old"),
        ]
    )
    calls = []

    def fetch_missing():
        calls.append("called")
        return [
            DailyMetric("gold", "AU9999", "close", "2026-01-02", 531.0, "akshare"),
            DailyMetric("gold", "AU9999", "close", "2026-04-30", 540.0, "akshare"),
            DailyMetric("gold", "AU9999", "close", "2026-05-04", 545.0, "akshare"),
        ]

    result = service.query_range(
        asset_type="gold",
        code="AU9999",
        metric="close",
        requested_from="2026-01-01",
        requested_to="2026-05-01",
        fetch_missing=fetch_missing,
    )

    assert calls == ["called"]
    assert result.actual_start_date == "2026-01-02"
    assert result.actual_end_date == "2026-04-30"
    assert result.data == [
        ("2026-01-02", 531.0, "akshare"),
        ("2026-04-30", 540.0, "akshare"),
    ]


def test_query_range_raises_when_no_data_exists_after_fetch(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)

    try:
        service.query_range(
            asset_type="bond",
            code="CN10Y",
            metric="yield",
            requested_from="2026-01-01",
            requested_to="2026-05-01",
            fetch_missing=lambda: [
                DailyMetric("bond", "CN10Y", "yield", "2025-12-31", 1.8, "akshare"),
            ],
        )
    except ValueError as exc:
        assert "No data available for bond CN10Y yield between 2026-01-01 and 2026-05-01" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_query_range_rejects_from_after_to(tmp_path):
    repo = InMemoryMetricsRepository()
    service = MetricsService(repo)

    try:
        service.query_range(
            asset_type="index",
            code="000300",
            metric="rolling_pe",
            requested_from="2026-05-01",
            requested_to="2026-01-01",
            fetch_missing=fail_fetch,
        )
    except ValueError as exc:
        assert "from date must be on or before to date" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
```

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```bash
pytest tests/test_service.py -q
```

Expected: FAIL because `MetricsService` has no `query_range` method.

- [ ] **Step 3: Implement range result types and service method**

In `src/finance_cli/service.py`, add this dataclass after `MetricQueryResult`:

```python
@dataclass(frozen=True)
class MetricRangeQueryResult:
    asset_type: str
    code: str
    metric: str
    requested_from: str
    requested_to: str
    actual_start_date: str
    actual_end_date: str
    data: list[tuple[str, float, str]]
```

Add this method inside `MetricsService`, after `query_value(...)`:

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
        parsed_from = parse_query_date(requested_from)
        parsed_to = parse_query_date(requested_to)
        if parsed_from > parsed_to:
            raise ValueError("from date must be on or before to date")

        from_text = parsed_from.isoformat()
        to_text = parsed_to.isoformat()

        self.repository.initialize()
        rows = self.repository.metrics_between(
            asset_type,
            code,
            metric,
            from_text,
            to_text,
        )
        if not self._has_local_data_on_or_after(
            asset_type,
            code,
            metric,
            to_text,
        ):
            self.repository.upsert_metrics(list(fetch_missing()))
            rows = self.repository.metrics_between(
                asset_type,
                code,
                metric,
                from_text,
                to_text,
            )

        if not rows:
            raise ValueError(
                f"No data available for {asset_type} {code} {metric} between {from_text} and {to_text}"
            )

        return MetricRangeQueryResult(
            asset_type=asset_type,
            code=code,
            metric=metric,
            requested_from=from_text,
            requested_to=to_text,
            actual_start_date=rows[0].date,
            actual_end_date=rows[-1].date,
            data=[(row.date, row.value, row.source) for row in rows],
        )
```

- [ ] **Step 4: Run service tests and verify they pass**

Run:

```bash
pytest tests/test_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit service changes**

Run:

```bash
git diff -- src/finance_cli/service.py tests/test_service.py
git add -p src/finance_cli/service.py tests/test_service.py
git commit -m "feat: add metric range service query"
```

Expected: commit includes only range service changes and tests.

---

### Task 2: Range Output Formatting

**Files:**
- Modify: `src/finance_cli/output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write failing output tests**

In `tests/test_output.py`, update the import:

```python
from finance_cli.output import format_json, format_range_json, format_range_text, format_text
from finance_cli.service import MetricQueryResult, MetricRangeQueryResult
```

Append these tests:

```python
def test_format_range_json_uses_stable_keys_and_raw_values_only():
    result = MetricRangeQueryResult(
        "index",
        "000300",
        "rolling_pe",
        "2026-01-01",
        "2026-05-01",
        "2026-01-02",
        "2026-04-30",
        [
            ("2026-01-02", 12.3, "akshare"),
            ("2026-04-30", 12.8, "akshare"),
        ],
    )

    payload = json.loads(format_range_json(result))

    assert set(payload) == {
        "asset_type",
        "code",
        "metric",
        "requested_from",
        "requested_to",
        "actual_start_date",
        "actual_end_date",
        "data",
    }
    assert payload["actual_start_date"] == "2026-01-02"
    assert payload["actual_end_date"] == "2026-04-30"
    assert payload["data"] == [
        {"date": "2026-01-02", "value": 12.3, "source": "akshare"},
        {"date": "2026-04-30", "value": 12.8, "source": "akshare"},
    ]
    assert "percentile" not in json.dumps(payload)
    assert "sample_count" not in json.dumps(payload)
    assert "lookback_years" not in json.dumps(payload)


def test_format_range_text_omits_percentile_fields():
    result = MetricRangeQueryResult(
        "gold",
        "AU9999",
        "close",
        "2026-01-01",
        "2026-05-01",
        "2026-01-02",
        "2026-04-30",
        [
            ("2026-01-02", 530.0, "akshare"),
            ("2026-04-30", 540.0, "akshare"),
        ],
    )

    text = format_range_text(result)

    assert "黄金: AU9999" in text
    assert "请求起始日期: 2026-01-01" in text
    assert "请求结束日期: 2026-05-01" in text
    assert "实际起始日期: 2026-01-02" in text
    assert "实际结束日期: 2026-04-30" in text
    assert "2026-01-02 530.0 akshare" in text
    assert "2026-04-30 540.0 akshare" in text
    assert "历史百分位" not in text
    assert "回看年数" not in text
    assert "样本数" not in text
    assert "样本起始日期" not in text
```

- [ ] **Step 2: Run output tests and verify they fail**

Run:

```bash
pytest tests/test_output.py -q
```

Expected: FAIL because `format_range_json` and `format_range_text` are missing.

- [ ] **Step 3: Implement range formatters**

In `src/finance_cli/output.py`, update the import:

```python
from .service import MetricQueryResult, MetricRangeQueryResult
```

Add these functions after `format_json(...)`:

```python
def format_range_json(result: MetricRangeQueryResult) -> str:
    payload = {
        "asset_type": result.asset_type,
        "code": result.code,
        "metric": result.metric,
        "requested_from": result.requested_from,
        "requested_to": result.requested_to,
        "actual_start_date": result.actual_start_date,
        "actual_end_date": result.actual_end_date,
        "data": [
            {"date": row_date, "value": value, "source": source}
            for row_date, value, source in result.data
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def format_range_text(result: MetricRangeQueryResult) -> str:
    label = _asset_label(result.asset_type)
    lines = [
        f"{label}: {result.code}",
        f"请求起始日期: {result.requested_from}",
        f"请求结束日期: {result.requested_to}",
        f"实际起始日期: {result.actual_start_date}",
        f"实际结束日期: {result.actual_end_date}",
        f"指标: {result.metric}",
    ]
    lines.extend(
        f"{row_date} {value} {source}"
        for row_date, value, source in result.data
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run output tests and verify they pass**

Run:

```bash
pytest tests/test_output.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit output changes**

Run:

```bash
git diff -- src/finance_cli/output.py tests/test_output.py
git add -p src/finance_cli/output.py tests/test_output.py
git commit -m "feat: format metric range output"
```

Expected: commit includes only output formatter changes and tests.

---

### Task 3: CLI Range Branches For PE, Gold, And CN10Y

**Files:**
- Modify: `src/finance_cli/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests for percentile commands**

Update the import in `tests/test_cli.py`:

```python
from finance_cli.service import MetricQueryResult, MetricRangeQueryResult
```

Append these tests:

```python
def test_pe_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update(
            {
                "asset_type": asset_type,
                "code": code,
                "metric": metric,
                "requested_from": requested_from,
                "requested_to": requested_to,
            }
        )
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-01-02", 12.3, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["pe", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {
        "asset_type": "index",
        "code": "000300",
        "metric": "rolling_pe",
        "requested_from": "2026-01-01",
        "requested_to": "2026-05-01",
    }
    payload = json.loads(result.output)
    assert payload["actual_start_date"] == "2026-01-02"
    assert payload["data"] == [{"date": "2026-01-02", "value": 12.3, "source": "akshare"}]
    assert "percentile" not in payload


def test_gold_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 540.0, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["gold", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "gold", "code": "AU9999", "metric": "close"}
    assert json.loads(result.output)["metric"] == "close"


def test_cn10y_yield_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.7, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["cn10y-yield", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "bond", "code": "CN10Y", "metric": "yield"}
    assert json.loads(result.output)["metric"] == "yield"
```

- [ ] **Step 2: Run new CLI tests and verify they fail**

Run:

```bash
pytest tests/test_cli.py::test_pe_command_outputs_range_json tests/test_cli.py::test_gold_command_outputs_range_json tests/test_cli.py::test_cn10y_yield_command_outputs_range_json -q
```

Expected: FAIL because the commands do not accept `--from/--to`.

- [ ] **Step 3: Add shared CLI helpers**

In `src/finance_cli/cli.py`, update the output import:

```python
from finance_cli.output import format_json, format_range_json, format_range_text, format_text
```

Add this helper near `_value_click_exception(...)`:

```python
def _is_range_mode(from_date: str | None, to_date: str | None) -> bool:
    return from_date is not None or to_date is not None


def _validate_range_options(
    from_date: str | None,
    to_date: str | None,
    query_date: str | None,
    years: int | None = None,
) -> tuple[str, str]:
    if from_date is None or to_date is None:
        raise JsonClickException("invalid_parameter", "--from and --to must be supplied together", exit_code=2)
    if query_date is not None:
        raise JsonClickException("invalid_parameter", "--date cannot be used with --from/--to", exit_code=2)
    if years is not None:
        raise JsonClickException("invalid_parameter", "--years cannot be used with --from/--to", exit_code=2)
    return from_date, to_date


def _default_query_date(query_date: str | None) -> str:
    return query_date or date.today().isoformat()


def _default_years(years: int | None) -> int:
    return 10 if years is None else years
```

- [ ] **Step 4: Add range branches to `pe`, `gold`, and `cn10y_yield`**

Change the `pe` signature so `query_date` and `years` are optional internally and add range options:

```python
def pe(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
```

At the start of `pe`, before the existing single-date query logic, add:

```python
    try:
        normalized_code = normalize_index_pe_code(code)
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "index",
                normalized_code,
                "rolling_pe",
                requested_from,
                requested_to,
                lambda: fetch_index_pe_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)
        result = _service().query(
```

Remove the old duplicate `validate_years(years)` and `normalized_code = normalize_index_pe_code(code)` from the original `try` block so the single-date branch continues from the new `result = _service().query(...)` call.

Apply the same pattern to `gold`:

```python
def gold(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
```

Range branch:

```python
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "gold",
                "AU9999",
                "close",
                requested_from,
                requested_to,
                fetch_gold_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
```

Apply the same pattern to `cn10y_yield` with `"bond"`, `"CN10Y"`, `"yield"`, and `fetch_cn10y_yield_rows`.

- [ ] **Step 5: Run CLI tests for these commands**

Run:

```bash
pytest tests/test_cli.py::test_pe_command_outputs_range_json tests/test_cli.py::test_gold_command_outputs_range_json tests/test_cli.py::test_cn10y_yield_command_outputs_range_json -q
```

Expected: PASS.

- [ ] **Step 6: Run existing single-date tests for these commands**

Run:

```bash
pytest tests/test_cli.py::test_pe_command_outputs_json tests/test_cli.py::test_gold_command_outputs_text tests/test_cli.py::test_cn10y_yield_command_outputs_json -q
```

Expected: PASS.

- [ ] **Step 7: Commit percentile-command CLI changes**

Run:

```bash
git diff -- src/finance_cli/cli.py tests/test_cli.py
git add -p src/finance_cli/cli.py tests/test_cli.py
git commit -m "feat: add range mode to percentile commands"
```

Expected: commit includes range CLI branches and tests for `pe`, `gold`, and `cn10y-yield`.

---

### Task 4: CLI Range Branches For Value Commands

**Files:**
- Modify: `src/finance_cli/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests for value commands**

Append these tests to `tests/test_cli.py`:

```python
def test_dividend_yield_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 2.3, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["dividend-yield", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "index", "code": "000300", "metric": "dividend_yield"}
    assert json.loads(result.output)["metric"] == "dividend_yield"


def test_pb_command_without_category_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 2.23, "etf.run")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(app, ["pb", "--code", "930707", "--from", "2026-01-01", "--to", "2026-05-01", "--json"])

    assert result.exit_code == 0
    assert seen == {"asset_type": "index", "code": "930707", "metric": "pb"}
    assert json.loads(result.output)["data"][0]["source"] == "etf.run"


def test_pb_command_with_category_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.8, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["pb", "--code", "801010", "--category", "一级行业", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "sw_index:一级行业", "code": "801010", "metric": "pb"}


def test_fund_nav_command_outputs_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.2456, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        ["fund-nav", "--code", "017763", "--from", "2026-01-01", "--to", "2026-05-01", "--json"],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "fund", "code": "017763", "metric": "unit_nav"}


def test_fund_nav_command_outputs_accumulated_range_json(monkeypatch, tmp_path):
    seen = {}

    def query_range(self, asset_type, code, metric, requested_from, requested_to, fetch_missing):
        seen.update({"asset_type": asset_type, "code": code, "metric": metric})
        return MetricRangeQueryResult(
            asset_type,
            code,
            metric,
            requested_from,
            requested_to,
            "2026-01-02",
            "2026-04-30",
            [("2026-04-30", 1.9876, "akshare")],
        )

    monkeypatch.setattr("finance_cli.service.MetricsService.query_range", query_range)

    result = runner.invoke(
        app,
        [
            "fund-nav",
            "--code",
            "017763",
            "--nav-type",
            "accumulated",
            "--from",
            "2026-01-01",
            "--to",
            "2026-05-01",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert seen == {"asset_type": "fund", "code": "017763", "metric": "accumulated_nav"}
```

- [ ] **Step 2: Run new value-command CLI tests and verify they fail**

Run:

```bash
pytest tests/test_cli.py::test_dividend_yield_command_outputs_range_json tests/test_cli.py::test_pb_command_without_category_outputs_range_json tests/test_cli.py::test_pb_command_with_category_outputs_range_json tests/test_cli.py::test_fund_nav_command_outputs_range_json tests/test_cli.py::test_fund_nav_command_outputs_accumulated_range_json -q
```

Expected: FAIL because value commands do not accept `--from/--to`.

- [ ] **Step 3: Add range branch to `dividend_yield`**

Change the signature:

```python
def dividend_yield(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
```

At the start of the `try` block:

```python
        normalized_code = normalize_csindex_code(code)
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            result = _service().query_range(
                "index",
                normalized_code,
                "dividend_yield",
                requested_from,
                requested_to,
                lambda: fetch_index_dividend_yield_rows(normalized_code),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
```

Keep the existing single-date `query_value(...)` path after this branch.

- [ ] **Step 4: Add range branch to `fund_nav`**

Change the signature:

```python
def fund_nav(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    nav_type: FundNavType = typer.Option(
        FundNavType.unit,
        "--nav-type",
        help="NAV type to query: unit or accumulated. Defaults to unit.",
    ),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
```

At the start of the `try` block after `metric` is computed:

```python
        normalized_code = normalize_fund_code(code)
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            result = _service().query_range(
                "fund",
                normalized_code,
                metric,
                requested_from,
                requested_to,
                lambda: fetch_fund_nav_rows(normalized_code, nav_type=nav_type.value),
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
```

Keep the existing single-date `query_value(...)` path after this branch.

- [ ] **Step 5: Add range branch to `pb`**

Change the signature:

```python
def pb(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    category: str | None = typer.Option(None, "--category"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
```

At the start of the `try` block:

```python
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date)
            if category is None:
                result = _service().query_range(
                    "index",
                    code,
                    "pb",
                    requested_from,
                    requested_to,
                    lambda: fetch_index_pb_rows(code),
                )
            else:
                _validate_sw_category(category)
                result = _service().query_range(
                    f"sw_index:{category}",
                    code,
                    "pb",
                    requested_from,
                    requested_to,
                    lambda: fetch_sw_index_pb_rows(code, category),
                )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
```

Keep the existing single-date branches after this range branch.

- [ ] **Step 6: Run value-command CLI tests**

Run:

```bash
pytest tests/test_cli.py::test_dividend_yield_command_outputs_range_json tests/test_cli.py::test_pb_command_without_category_outputs_range_json tests/test_cli.py::test_pb_command_with_category_outputs_range_json tests/test_cli.py::test_fund_nav_command_outputs_range_json tests/test_cli.py::test_fund_nav_command_outputs_accumulated_range_json -q
```

Expected: PASS.

- [ ] **Step 7: Run existing single-date value-command tests**

Run:

```bash
pytest tests/test_cli.py::test_dividend_yield_command_outputs_json tests/test_cli.py::test_pb_command_outputs_text tests/test_cli.py::test_pb_command_without_category_queries_index_pb tests/test_cli.py::test_fund_nav_command_outputs_unit_nav_json tests/test_cli.py::test_fund_nav_command_supports_accumulated_nav -q
```

Expected: PASS.

- [ ] **Step 8: Commit value-command CLI changes**

Run:

```bash
git diff -- src/finance_cli/cli.py tests/test_cli.py
git add -p src/finance_cli/cli.py tests/test_cli.py
git commit -m "feat: add range mode to value commands"
```

Expected: commit includes range CLI branches and tests for `dividend-yield`, `pb`, and `fund-nav`.

---

### Task 5: Range Parameter Errors

**Files:**
- Modify: `src/finance_cli/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing parameter validation tests**

Append these tests to `tests/test_cli.py`:

```python
def test_range_mode_requires_from_and_to(monkeypatch, tmp_path):
    result = runner.invoke(app, ["gold", "--from", "2026-01-01", "--json"])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "--from and --to must be supplied together",
        }
    }


def test_range_mode_rejects_explicit_date(monkeypatch, tmp_path):
    result = runner.invoke(
        app,
        ["gold", "--from", "2026-01-01", "--to", "2026-05-01", "--date", "2026-04-20", "--json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "--date cannot be used with --from/--to",
        }
    }


def test_range_mode_rejects_explicit_years(monkeypatch, tmp_path):
    result = runner.invoke(
        app,
        ["pe", "--code", "000300", "--from", "2026-01-01", "--to", "2026-05-01", "--years", "5", "--json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "--years cannot be used with --from/--to",
        }
    }


def test_range_mode_rejects_from_after_to(monkeypatch, tmp_path):
    result = runner.invoke(
        app,
        ["gold", "--from", "2026-05-01", "--to", "2026-01-01", "--json"],
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "error": {
            "code": "invalid_parameter",
            "message": "from date must be on or before to date",
        }
    }
```

- [ ] **Step 2: Run validation tests**

Run:

```bash
pytest tests/test_cli.py::test_range_mode_requires_from_and_to tests/test_cli.py::test_range_mode_rejects_explicit_date tests/test_cli.py::test_range_mode_rejects_explicit_years tests/test_cli.py::test_range_mode_rejects_from_after_to -q
```

Expected: the first three tests PASS if Task 3 helpers are already correct; `from_after_to` may FAIL with `runtime_error` until the next step.

- [ ] **Step 3: Classify range date-order validation as invalid parameter**

In `src/finance_cli/cli.py`, update `_value_click_exception(...)`:

```python
def _value_click_exception(exc: ValueError) -> JsonClickException:
    message = str(exc)
    if (
        message.startswith("Years must")
        or message.startswith("category must")
        or message == "from date must be on or before to date"
        or message == "Date must use YYYY-MM-DD format"
    ):
        return JsonClickException("invalid_parameter", message, exit_code=2)
    return JsonClickException("runtime_error", message)
```

- [ ] **Step 4: Run validation tests again**

Run:

```bash
pytest tests/test_cli.py::test_range_mode_requires_from_and_to tests/test_cli.py::test_range_mode_rejects_explicit_date tests/test_cli.py::test_range_mode_rejects_explicit_years tests/test_cli.py::test_range_mode_rejects_from_after_to -q
```

Expected: PASS.

- [ ] **Step 5: Commit validation changes**

Run:

```bash
git diff -- src/finance_cli/cli.py tests/test_cli.py
git add -p src/finance_cli/cli.py tests/test_cli.py
git commit -m "fix: validate range query parameters"
```

Expected: commit includes range parameter validation and tests.

---

### Task 6: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README range examples**

In `README.md`, after the existing "Output JSON" example, add:

````markdown
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
````

- [ ] **Step 2: Run the full test suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 3: Inspect final diff for scope**

Run:

```bash
git diff --stat
git diff -- README.md src/finance_cli/service.py src/finance_cli/output.py src/finance_cli/cli.py tests/test_service.py tests/test_output.py tests/test_cli.py
```

Expected: diff only implements range query support, output formatting, tests, and README examples.

- [ ] **Step 4: Commit docs and any remaining feature hunks**

Run:

```bash
git add -p README.md src/finance_cli/service.py src/finance_cli/output.py src/finance_cli/cli.py tests/test_service.py tests/test_output.py tests/test_cli.py
git commit -m "docs: document range queries"
```

Expected: commit contains README updates and any remaining unstaged range-query hunks.

- [ ] **Step 5: Confirm repository state**

Run:

```bash
git status --short
```

Expected: no unstaged range-query changes remain. Pre-existing unrelated changes may still appear if they were not part of this feature.
