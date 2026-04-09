import typer
from rich import print as rprint
from rich.table import Table
from rich.console import Console
import subprocess, sys, os
import httpx, sys, platform
from pathlib import Path

from elio.cli import app
from elio.auth.manager import (
    set_api_key, get_api_key, logout_all, get_connected_providers, PROVIDERS
)
from elio.config.loader import load_config, get_config_path

console = Console()

# ──────────────────────────────────────────────
# elio login
# ──────────────────────────────────────────────
@app.command()
def login():
    """Add or update API keys for AI providers."""
    rprint("\n[bold cyan]Elio Login[/bold cyan] — connect your AI providers\n")

    choices = {
        "1": ("anthropic", "Anthropic (Claude)", "sk-ant-..."),
        "2": ("openai",    "OpenAI (ChatGPT)",  "sk-..."),
        "3": ("google",    "Google (Gemini)",   "AIza..."),
    }

    rprint("[dim]Which provider do you want to configure?[/dim]")
    for k, (_, label, hint) in choices.items():
        rprint(f"  [{k}] {label}  [dim]({hint})[/dim]")
    rprint("  [A] All providers\n")

    choice = typer.prompt("Select").strip().upper()

    selected = (
        [v for v in choices.values()] if choice == "A"
        else [choices[choice]] if choice in choices
        else []
    )

    if not selected:
        rprint("[red]Invalid choice.[/red]")
        raise typer.Exit(1)

    for provider, label, _ in selected:
        key = typer.prompt(f"Paste your {label} API key", hide_input=True)
        if not key.strip():
            rprint("[yellow]Skipped (empty).[/yellow]")
            continue
        try:
            set_api_key(provider, key)
            rprint(f"[green]✓ {label} key saved.[/green]")
        except Exception as e:
            rprint(f"[red]Failed to save {label} key: {e}[/red]")

    rprint("\n[bold]Run [cyan]elio status[/cyan] to verify, then [cyan]elio[/cyan] to start chatting.[/bold]\n")


# ──────────────────────────────────────────────
# elio logout
# ──────────────────────────────────────────────
@app.command()
def logout():
    """Remove all stored credentials from the OS keyring."""
    confirm = typer.confirm("This will remove ALL stored API keys. Continue?")
    if confirm:
        logout_all()
        rprint("[green]All credentials removed.[/green]")


# ──────────────────────────────────────────────
# elio status
# ──────────────────────────────────────────────
@app.command()
def status():
    """Check which AI providers are connected."""
    table = Table(title="Elio Provider Status", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Status")
    table.add_column("Key Preview", style="dim")

    for p in PROVIDERS:
        key = get_api_key(p)
        if key:
            preview = key[:8] + "..." + key[-4:]
            table.add_row(p.capitalize(), "[green]✓ Connected[/green]", preview)
        else:
            table.add_row(p.capitalize(), "[red]✗ Not configured[/red]", "—")

    console.print(table)


# ──────────────────────────────────────────────
# elio config
# ──────────────────────────────────────────────
@app.command()
def config():
    """Open the config file in your default editor."""
    path = get_config_path()
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(path)])

CURRENT_VERSION = "0.1.0"
RELEASES_API = "https://api.github.com/repos/Elio-labs/elio/releases/latest"


@app.command()
def update():
    """Check for a newer version and install it if available."""
    rprint("[cyan]Checking for updates...[/cyan]")
    try:
        resp = httpx.get(RELEASES_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        latest = data["tag_name"].lstrip("v")

        if latest <= CURRENT_VERSION:
            rprint(f"[green]Already on latest version ({CURRENT_VERSION}).[/green]")
            return

        rprint(f"[yellow]New version available: {latest}[/yellow]")

        # Find the right asset for this platform
        os_map = {"Windows": ".exe", "Darwin": ".dmg", "Linux": ".deb"}
        ext = os_map.get(platform.system(), ".AppImage")
        assets = [a for a in data["assets"] if a["name"].endswith(ext)]

        if not assets:
            rprint(f"[red]No installer found for {platform.system()}. Visit the website.[/red]")
            return

        download_url = assets[0]["browser_download_url"]
        rprint(f"Downloading from {download_url}...")

        with httpx.stream("GET", download_url, follow_redirects=True) as r:
            installer_path = Path.home() / f"elio-update{ext}"
            with open(installer_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

        rprint(f"[green]Downloaded to {installer_path}. Run it to complete the update.[/green]")

    except Exception as e:
        rprint(f"[red]Update check failed: {e}[/red]")

@app.command()
def models():
    """List all available AI models and their aliases."""
    from elio.providers.registry import MODEL_REGISTRY

    table = Table(title="Elio Model Registry")
    table.add_column("Alias",       style="cyan",   width=12)
    table.add_column("Model String", style="green",  width=28)
    table.add_column("Provider",     style="yellow", width=12)
    table.add_column("Description")

    for alias, entry in MODEL_REGISTRY.items():
        table.add_row(alias, entry.model_string, entry.provider_name, entry.description)

    console.print(table)
    console.print("\n[dim]Switch with: /model [alias]  or  elio --model [alias][/dim]")

@app.command()
def history():
    """Browse your saved conversation sessions."""
    from elio.session.history import init_db, list_sessions

    init_db()
    sessions = list_sessions(limit=30)

    if not sessions:
        rprint("[yellow]No sessions yet. Start chatting with `elio`.[/yellow]")
        return

    table = Table(title="Recent Sessions")
    table.add_column("ID",      style="cyan",   width=10)
    table.add_column("Title",   style="white",  width=30)
    table.add_column("Model",   style="green",  width=20)
    table.add_column("Updated", style="yellow")

    for s in sessions:
        table.add_row(s["id"], s["title"], s["model"], s["updated"][:16])

    console.print(table)
    console.print("\n[dim]Resume a session: elio  then  /load [id][/dim]")