from datetime import date
from typing import Annotated

import click
import typer

from finance_cli.analytics import validate_years
from finance_cli.config import resolve_db_path
from finance_cli.db import MetricsRepository
from finance_cli.output import format_json, format_text
from finance_cli.service import MetricsService
from finance_cli.sources import (
    DataSourceError,
    fetch_cn10y_yield_rows,
    fetch_gold_rows,
    fetch_index_dividend_yield_rows,
    fetch_index_pe_rows,
    fetch_sw_index_pb_rows,
)


app = typer.Typer(help="Financial data CLI")
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")
SW_INDEX_CATEGORIES = ("市场表征", "一级行业", "二级行业", "风格指数")


def _service() -> MetricsService:
    return MetricsService(MetricsRepository(resolve_db_path()))


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
    """Query index PE-TTM percentile."""
    try:
        validate_years(years)
        result = _service().query(
            "index",
            code,
            "pe_ttm",
            query_date,
            years,
            lambda: fetch_index_pe_rows(code),
        )
    except DataSourceError as exc:
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
    years: int = typer.Option(10, "--years"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query index dividend-yield percentile."""
    try:
        validate_years(years)
        result = _service().query(
            "index",
            code,
            "dividend_yield",
            query_date,
            years,
            lambda: fetch_index_dividend_yield_rows(code),
        )
    except DataSourceError as exc:
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
    category: str = typer.Option(..., "--category"),
    years: int = typer.Option(10, "--years"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Query SW index PB percentile."""
    try:
        validate_years(years)
        _validate_sw_category(category)
        result = _service().query(
            f"sw_index:{category}",
            code,
            "pb",
            query_date,
            years,
            lambda: fetch_sw_index_pb_rows(code, category),
        )
    except DataSourceError as exc:
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
    except DataSourceError as exc:
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
    except DataSourceError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(format_json(result) if json_output else format_text(result))


@sync_app.command("pe")
def sync_pe(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index PE-TTM history."""
    try:
        inserted = _service().sync(lambda: fetch_index_pe_rows(code))
    except DataSourceError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("dividend-yield")
def sync_dividend_yield(code: str = typer.Option(..., "--code")) -> None:
    """Synchronize index dividend-yield history."""
    try:
        inserted = _service().sync(lambda: fetch_index_dividend_yield_rows(code))
    except DataSourceError as exc:
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
    except DataSourceError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("gold")
def sync_gold() -> None:
    """Synchronize Au9999 gold price history."""
    try:
        inserted = _service().sync(fetch_gold_rows)
    except DataSourceError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


@sync_app.command("cn10y-yield")
def sync_cn10y_yield() -> None:
    """Synchronize China 10-year government bond yield history."""
    try:
        inserted = _service().sync(fetch_cn10y_yield_rows)
    except DataSourceError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"同步 {inserted} 条记录")


def _validate_sw_category(category: str) -> None:
    if category not in SW_INDEX_CATEGORIES:
        allowed = ", ".join(SW_INDEX_CATEGORIES)
        raise ValueError(f"category must be one of: {allowed}")
