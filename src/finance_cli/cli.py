from datetime import date
from enum import Enum
import json
import sys
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

from finance_cli.analytics import validate_years
from finance_cli.config import load_config
from finance_cli.db import MetricsRepository, SQLiteApiError
from finance_cli.output import format_json, format_range_json, format_range_text, format_text
from finance_cli.service import MetricsService
from finance_cli.sources import (
    DataSourceError,
    fetch_cn10y_yield_rows,
    fetch_gold_rows,
    fetch_fund_nav_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_pb_rows,
    fetch_index_pe_rows,
    normalize_index_pe_code,
    normalize_csindex_code,
    fetch_sw_index_pb_rows,
    normalize_fund_code,
)


class JsonClickException(click.ClickException):
    def __init__(self, error_code: str, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.exit_code = exit_code


class JsonErrorGroup(TyperGroup):
    def main(
        self,
        args: list[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: object,
    ) -> object:
        current_args = list(sys.argv[1:] if args is None else args)
        wants_json = "--json" in current_args
        try:
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                **extra,
            )
        except click.ClickException as exc:
            if wants_json:
                click.echo(_format_error_json(exc))
            else:
                exc.show()
            if standalone_mode:
                raise SystemExit(exc.exit_code) from exc
            if wants_json:
                return exc.exit_code
            raise


app = typer.Typer(help="Financial data CLI", cls=JsonErrorGroup)
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")
SW_INDEX_CATEGORIES = ("市场表征", "一级行业", "二级行业", "风格指数")


class FundNavType(str, Enum):
    unit = "unit"
    accumulated = "accumulated"


def _service() -> MetricsService:
    config = load_config()
    return MetricsService(MetricsRepository(config.sqlite_api_host, config.sqlite_db))


def _format_error_json(exc: click.ClickException) -> str:
    error_code = getattr(exc, "error_code", None) or _default_error_code(exc)
    return json.dumps(
        {"error": {"code": error_code, "message": exc.format_message()}},
        ensure_ascii=False,
    )


def _default_error_code(exc: click.ClickException) -> str:
    if isinstance(exc, click.UsageError):
        return "invalid_parameter"
    return "runtime_error"


def _runtime_click_exception(exc: DataSourceError | SQLiteApiError) -> JsonClickException:
    if isinstance(exc, SQLiteApiError):
        return JsonClickException("sqlite_api_error", str(exc))
    message = str(exc)
    if message.startswith("Invalid ") or message.startswith("PB without --category"):
        return JsonClickException("invalid_parameter", message)
    return JsonClickException("runtime_error", message)


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


@app.command()
def pe(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index rolling PE percentile."""
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
            "index",
            normalized_code,
            "rolling_pe",
            query_date,
            years,
            lambda: fetch_index_pe_rows(normalized_code),
            ensure_lookback_coverage=True,
            minimum_lookback_years=3,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("dividend-yield")
def dividend_yield(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index dividend-yield value."""
    try:
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
        result = _service().query_value(
            "index",
            normalized_code,
            "dividend_yield",
            query_date,
            lambda: fetch_index_dividend_yield_rows(normalized_code, query_date=query_date),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("fund-nav")
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
    """Query fund net asset value."""
    metric = "unit_nav" if nav_type == FundNavType.unit else "accumulated_nav"
    try:
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
        result = _service().query_value(
            "fund",
            normalized_code,
            metric,
            query_date,
            lambda: fetch_fund_nav_rows(normalized_code, nav_type=nav_type.value),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command()
def pb(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    code: str = typer.Option(..., "--code"),
    category: str | None = typer.Option(None, "--category"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index PB value."""
    try:
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
        if category is None:
            result = _service().query_value(
                "index",
                code,
                "pb",
                query_date,
                lambda: fetch_index_pb_rows(code),
            )
        else:
            _validate_sw_category(category)
            result = _service().query_value(
                f"sw_index:{category}",
                code,
                "pb",
                query_date,
                lambda: fetch_sw_index_pb_rows(code, category, query_date=query_date),
            )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command()
def gold(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query Au9999 gold close-price percentile."""
    try:
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
        validate_years(years)
        result = _service().query(
            "gold",
            "AU9999",
            "close",
            query_date,
            years,
            fetch_gold_rows,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("cn10y-yield")
def cn10y_yield(
    query_date: Annotated[str | None, typer.Option("--date")] = None,
    years: int | None = typer.Option(None, "--years"),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query China 10-year government bond yield percentile."""
    try:
        if _is_range_mode(from_date, to_date):
            requested_from, requested_to = _validate_range_options(from_date, to_date, query_date, years)
            result = _service().query_range(
                "bond",
                "CN10Y",
                "yield",
                requested_from,
                requested_to,
                fetch_cn10y_yield_rows,
            )
            typer.echo(format_range_json(result) if json_output else format_range_text(result))
            return

        query_date = _default_query_date(query_date)
        years = _default_years(years)
        validate_years(years)
        result = _service().query(
            "bond",
            "CN10Y",
            "yield",
            query_date,
            years,
            fetch_cn10y_yield_rows,
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@sync_app.command("pe")
def sync_pe(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index rolling PE history."""
    try:
        normalized_code = normalize_index_pe_code(code)
        if normalized_code == "NDX":
            inserted = _service().replace_sync(
                "index",
                normalized_code,
                "rolling_pe",
                lambda: fetch_index_pe_rows(normalized_code),
            )
        else:
            inserted = _service().sync(lambda: fetch_index_pe_rows(normalized_code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("dividend-yield")
def sync_dividend_yield(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index dividend-yield history."""
    try:
        normalized_code = normalize_csindex_code(code)
        inserted = _service().sync(lambda: fetch_index_dividend_yield_rows(normalized_code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("pb")
def sync_pb(
    code: str = typer.Option(..., "--code"),
    category: str = typer.Option(..., "--category"),
) -> None:
    """Synchronize SW index PB history."""
    try:
        _validate_sw_category(category)
        inserted = _service().sync(lambda: fetch_sw_index_pb_rows(code, category))
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold")
def sync_gold() -> None:
    """Synchronize Au9999 gold price history."""
    try:
        inserted = _service().sync(fetch_gold_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("cn10y-yield")
def sync_cn10y_yield() -> None:
    """Synchronize China 10-year government bond yield history."""
    try:
        inserted = _service().sync(fetch_cn10y_yield_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise _runtime_click_exception(exc) from exc
    except ValueError as exc:
        raise _value_click_exception(exc) from exc

    typer.echo(f"同步 {inserted} 条记录")


def _validate_sw_category(category: str) -> None:
    if category not in SW_INDEX_CATEGORIES:
        allowed = ", ".join(SW_INDEX_CATEGORIES)
        raise ValueError(f"category must be one of: {allowed}")
