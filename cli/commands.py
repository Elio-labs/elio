import os
import sys
import platform
import subprocess

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from auth.manager import (
    set_api_key, get_api_key, delete_api_key,
    get_connected_providers, logout_all, PROVIDERS,
)

console = Console()

CURRENT_VERSION = "0.2.6"
GITHUB_API = "https://api.github.com/repos/Elio-labs/elio/releases/latest"


# ──────────────────────────────────────────────
# run_login — interactive key entry
# ──────────────────────────────────────────────

def run_login(provider: str | None = None):
    """Prompt the user to add API keys."""
    if provider:
        if provider not in PROVIDERS:
            console.print(f"[red]Unknown provider '{provider}'. Must be one of {PROVIDERS}[/red]")
            return
        providers_to_add = [provider]
    else:
        providers_to_add = PROVIDERS

    console.print()
    console.print("[bold #6c71c4]Elio — API Key Setup[/bold #6c71c4]")
    console.print("[dim]Keys are stored securely in your OS keyring (never in plain text).[/dim]")
    console.print()

    provider_help = {
        "anthropic": ("console.anthropic.com",  "Settings → API Keys",          "sk-ant-"),
        "google":    ("aistudio.google.com",     "Get API Key → Create API Key", "AIza"),
        "openai":    ("platform.openai.com",     "Profile → API Keys",           "sk-"),
    }

    for p in providers_to_add:
        existing = get_api_key(p)
        status = "[green]●[/green]" if existing else "[dim]○[/dim]"
        url, path, prefix = provider_help.get(p, ("", "", ""))

        console.print(f"  {status} [bold]{p.capitalize()}[/bold]")
        if url:
            console.print(f"     [dim]Get key at: {url}  ({path})[/dim]")
            console.print(f"     [dim]Key starts with: {prefix}...[/dim]")

        import getpass
        try:
            if existing:
                raw = getpass.getpass(f"     New key (Enter to keep existing): ")
            else:
                raw = getpass.getpass(f"     Paste API key (Enter to skip): ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Skipped.[/dim]")
            continue

        key = raw.strip()
        if key:
            set_api_key(p, key)
            console.print(f"     [green]✓ Saved.[/green]")
        elif existing:
            console.print(f"     [dim]Kept existing key.[/dim]")
        else:
            console.print(f"     [dim]Skipped.[/dim]")

        console.print()

    console.print("[bold green]Done![/bold green] Run [bold cyan]elio[/bold cyan] to start chatting.\n")


# ──────────────────────────────────────────────
# run_logout
# ──────────────────────────────────────────────

def run_logout():
    """Remove all stored API keys."""
    logout_all()
    console.print("[green]✓ All credentials removed.[/green]")


# ──────────────────────────────────────────────
# run_status
# ──────────────────────────────────────────────

def run_status():
    """Show which providers are configured."""
    from providers.registry import PROVIDERS as PROV_INFO, PROVIDER_ORDER

    table = Table(title="Provider Status", border_style="#6c71c4")
    table.add_column("Provider", style="cyan")
    table.add_column("Brand",    style="white")
    table.add_column("Status")
    table.add_column("Free Tier")

    for key in PROVIDER_ORDER:
        info = PROV_INFO[key]
        has_key = get_api_key(key) is not None
        status = "[green]● Connected[/green]" if has_key else "[dim]○ Not configured[/dim]"
        free   = "[green]Yes[/green]" if info.has_free else "[dim]No[/dim]"
        table.add_row(info.name, info.brand, status, free)

    console.print(table)
    console.print("\n  [dim]Run [bold cyan]elio login[/bold cyan] to add missing keys.[/dim]\n")


# ──────────────────────────────────────────────
# run_models
# ──────────────────────────────────────────────

def run_models():
    """List all available models across all providers."""
    from providers.registry import (
        MODEL_REGISTRY, PROVIDER_ORDER, PROVIDER_MODELS, PROVIDERS as PROV_INFO,
    )

    for provider_key in PROVIDER_ORDER:
        info    = PROV_INFO[provider_key]
        aliases = PROVIDER_MODELS.get(provider_key, [])

        table = Table(
            title=f"{info.name} ({info.brand})",
            border_style="#6c71c4",
        )
        table.add_column("Alias",       style="cyan bold")
        table.add_column("Model ID",    style="white")
        table.add_column("Tier",        width=6)
        table.add_column("Description", style="dim")

        for alias in aliases:
            entry = MODEL_REGISTRY[alias]
            tier  = "[green]Free[/green]" if entry.is_free else "[yellow]Paid[/yellow]"
            table.add_row(entry.alias, entry.model_string, tier, entry.description)

        console.print(table)
        console.print()


# ──────────────────────────────────────────────
# run_history
# ──────────────────────────────────────────────

def run_history():
    """Show recent chat sessions."""
    from session.history import init_db, list_sessions

    init_db()
    sessions = list_sessions()
    if not sessions:
        console.print("[dim]No saved sessions yet.[/dim]")
        return

    table = Table(title="Recent Sessions", border_style="#6c71c4")
    table.add_column("ID",           style="cyan")
    table.add_column("Title",        style="white")
    table.add_column("Model",        style="yellow")
    table.add_column("Last Updated", style="dim")

    for s in sessions:
        table.add_row(s["id"], s["title"], s["model"], s["updated"][:16])

    console.print(table)


# ──────────────────────────────────────────────
# run_config
# ──────────────────────────────────────────────

def run_config():
    """Open the config file in the user's editor."""
    from config.loader import get_config_path, ensure_elio_dir

    ensure_elio_dir()
    path = get_config_path()

    if not path.exists():
        from config.loader import load_config
        load_config()

    console.print(f"[dim]Config file: {path}[/dim]")

    if platform.system() == "Windows":
        os.startfile(str(path))
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(path)])


# ──────────────────────────────────────────────
# run_update — silent in-place installer update
# ──────────────────────────────────────────────

def run_update():
    """
    Update Elio in-place by upgrading via pip.
    """
    console.print()
    console.print("[dim]Checking for updates via pip...[/dim]")

    try:
        # Run pip upgrade silently but show progress line
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "elio-cli"],
            capture_output=True, text=True, check=True
        )
        
        console.print("[green]✓ Output from pip:[/green]")
        
        # Determine if it was already up to date
        if "Requirement already satisfied" in result.stdout and "Successfully installed" not in result.stdout:
            console.print("[dim]You are already on the latest version of Elio.[/dim]")
        else:
            console.print("[bold green]Elio has been updated successfully![/bold green]")
            console.print("[dim]Close this terminal and open a new one to use the latest version.[/dim]")
            
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Update failed with error code {e.returncode}[/red]")
        console.print("[dim]Details:[/dim]")
        console.print(e.stderr)
    except Exception as e:
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
