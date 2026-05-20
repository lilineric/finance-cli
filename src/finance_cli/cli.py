from datetime import date
from typing import Annotated

import click
import typer

from finance_cli.analytics import validate_years
from finance_cli.config import resolve_db_path
from finance_cli.db import MetricsRepository
from finance_cli.output import format_json, format_text
from finance_cli.service import MetricsService
from finance_cli.sources import DataSourceError, fetch_gold_rows, fetch_index_pe_rows


app = typer.Typer(help="Financial data CLI")
sync_app = typer.Typer(help="Synchronize local data")
app.add_typer(sync_app, name="sync")


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
