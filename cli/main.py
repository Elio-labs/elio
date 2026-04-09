"""
Elio CLI — Main entry point.
All subcommands and the default `elio` (chat) command live here.
"""

import typer
import asyncio
import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

app = typer.Typer(
    name="elio",
    help="Unified AI CLI — Claude, Gemini, and ChatGPT in one terminal.",
    add_completion=False,
    no_args_is_help=False,
)

console = Console()

VERSION = "0.2.5"


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]Elio[/bold cyan] version [bold]{VERSION}[/bold]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """
    Elio — Unified AI CLI. Run without a subcommand to open the chat interface.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand → launch TUI chat
        _check_credentials_before_chat()
        from tui.app import ElioApp
        app_instance = ElioApp()
        app_instance.run()


def _check_credentials_before_chat():
    """Warn if no providers are configured, offer to run login."""
    from auth.manager import AuthManager
    mgr = AuthManager()
    providers = mgr.get_configured_providers()
    if not providers:
        console.print(Panel(
            "[yellow]No AI providers configured.[/yellow]\n\n"
            "Run [bold cyan]elio login[/bold cyan] to add your API keys.",
            title="[bold red]Setup Required[/bold red]",
            border_style="red",
        ))
        raise typer.Exit(1)


# ──────────────────────────────────────────────
# Subcommands
# ──────────────────────────────────────────────

@app.command()
def login(
    provider: Optional[str] = typer.Argument(None, help="Provider: anthropic, google, openai")
):
    """Add or update API keys for AI providers."""
    from cli.commands import run_login
    run_login(provider)


@app.command()
def logout():
    """Remove all stored credentials."""
    from cli.commands import run_logout
    run_logout()


@app.command()
def status():
    """Check which AI providers are connected."""
    from cli.commands import run_status
    run_status()


@app.command()
def models():
    """List all available models."""
    from cli.commands import run_models
    run_models()


@app.command()
def history():
    """Browse saved conversation sessions."""
    from cli.commands import run_history
    run_history()


@app.command()
def config():
    """Open the Elio config file in your default editor."""
    from cli.commands import run_config
    run_config()


@app.command()
def update():
    """Check for and install the latest version of Elio."""
    from cli.commands import run_update
    run_update()


if __name__ == "__main__":
    app()