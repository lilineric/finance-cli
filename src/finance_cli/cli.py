from datetime import date
from typing import Annotated

import click
import typer

from finance_cli.analytics import validate_years
from finance_cli.config import load_config
from finance_cli.db import MetricsRepository, SQLiteApiError
from finance_cli.output import format_json, format_text
from finance_cli.service import MetricsService
from finance_cli.sources import (
    DataSourceError,
    fetch_cn10y_yield_rows,
    fetch_gold_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_pb_rows,
    fetch_index_pe_rows,
    normalize_index_pe_code,
    normalize_csindex_code,
    fetch_sw_index_pb_rows,
)


app = typer.Typer(help="Financial data CLI")
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")
SW_INDEX_CATEGORIES = ("市场表征", "一级行业", "二级行业", "风格指数")


def _service() -> MetricsService:
    config = load_config()
    return MetricsService(MetricsRepository(config.sqlite_api_host, config.sqlite_db))


@app.command()
def pe(
    query_date: Annotated[
        str,
        typer.Option("--date", default_factory=lambda: date.today().isoformat()),
    ],
    code: str = typer.Option(..., "--code"),
    years: int = typer.Option(10, "--years"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index rolling PE percentile."""
    try:
        validate_years(years)
        normalized_code = normalize_index_pe_code(code)
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
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("dividend-yield")
def dividend_yield(
    query_date: Annotated[
        str,
        typer.Option("--date", default_factory=lambda: date.today().isoformat()),
    ],
    code: str = typer.Option(..., "--code"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index dividend-yield value."""
    try:
        normalized_code = normalize_csindex_code(code)
        result = _service().query_value(
            "index",
            normalized_code,
            "dividend_yield",
            query_date,
            lambda: fetch_index_dividend_yield_rows(normalized_code, query_date=query_date),
        )
    except (DataSourceError, SQLiteApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command()
def pb(
    query_date: Annotated[
        str,
        typer.Option("--date", default_factory=lambda: date.today().isoformat()),
    ],
    code: str = typer.Option(..., "--code"),
    category: str | None = typer.Option(None, "--category"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index PB value."""
    try:
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
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command()
def gold(
    query_date: Annotated[
        str,
        typer.Option("--date", default_factory=lambda: date.today().isoformat()),
    ],
    years: int = typer.Option(10, "--years"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query Au9999 gold close-price percentile."""
    try:
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
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@app.command("cn10y-yield")
def cn10y_yield(
    query_date: Annotated[
        str,
        typer.Option("--date", default_factory=lambda: date.today().isoformat()),
    ],
    years: int = typer.Option(10, "--years"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query China 10-year government bond yield percentile."""
    try:
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
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@sync_app.command("pe")
def sync_pe(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index rolling PE history."""
    try:
        normalized_code = normalize_index_pe_code(code)
        inserted = _service().sync(lambda: fetch_index_pe_rows(normalized_code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("dividend-yield")
def sync_dividend_yield(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index dividend-yield history."""
    try:
        normalized_code = normalize_csindex_code(code)
        inserted = _service().sync(lambda: fetch_index_dividend_yield_rows(normalized_code))
    except (DataSourceError, SQLiteApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

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
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold")
def sync_gold() -> None:
    """Synchronize Au9999 gold price history."""
    try:
        inserted = _service().sync(fetch_gold_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("cn10y-yield")
def sync_cn10y_yield() -> None:
    """Synchronize China 10-year government bond yield history."""
    try:
        inserted = _service().sync(fetch_cn10y_yield_rows)
    except (DataSourceError, SQLiteApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


def _validate_sw_category(category: str) -> None:
    if category not in SW_INDEX_CATEGORIES:
        allowed = ", ".join(SW_INDEX_CATEGORIES)
        raise ValueError(f"category must be one of: {allowed}")
