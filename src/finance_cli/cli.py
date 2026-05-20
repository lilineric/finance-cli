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
