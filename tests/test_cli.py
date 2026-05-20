from typer.testing import CliRunner

from finance_cli.cli import app


runner = CliRunner()


def test_cli_help_shows_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pe" in result.output
    assert "gold" in result.output
    assert "sync" in result.output
