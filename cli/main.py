import typer
from typing import Optional
from elio.cli import app
import elio.cli.commands

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Start with a specific model alias"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
):
    if version:
        typer.echo("elio 0.2.3")
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    from elio.auth.manager import get_connected_providers
    if not get_connected_providers():
        typer.echo("No providers configured. Run `elio login` first.", err=True)
        raise typer.Exit(1)

    from elio.tui.app import run_tui
    run_tui(alias=model)

if __name__ == "__main__":
    app()