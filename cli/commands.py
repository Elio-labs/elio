import os
import sys
import platform
import subprocess
import tempfile
import httpx
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, DownloadColumn, TransferSpeedColumn, BarColumn, TextColumn

from auth.manager import (
    set_api_key, get_api_key, delete_api_key,
    get_connected_providers, logout_all, PROVIDERS,
)

console = Console()

CURRENT_VERSION = "0.1.0"
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

    for p in providers_to_add:
        existing = get_api_key(p)
        status = "[green]●[/green]" if existing else "[dim]○[/dim]"
        console.print(f"\n{status} [bold]{p}[/bold]")
        key = Prompt.ask(f"  Enter your {p} API key (leave blank to skip)", default="")
        if key.strip():
            set_api_key(p, key.strip())
            console.print(f"  [green]✓ {p} key saved.[/green]")
        elif existing:
            console.print(f"  [dim]Kept existing key.[/dim]")
        else:
            console.print(f"  [dim]Skipped.[/dim]")

    console.print("\n[bold green]Done![/bold green] Run [bold cyan]elio[/bold cyan] to start chatting.\n")


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
    connected = get_connected_providers()
    table = Table(title="Provider Status")
    table.add_column("Provider", style="cyan")
    table.add_column("Status")

    for p in PROVIDERS:
        if p in connected:
            table.add_row(p, "[green]● Connected[/green]")
        else:
            table.add_row(p, "[dim]○ Not configured[/dim]")

    console.print(table)


# ──────────────────────────────────────────────
# run_models
# ──────────────────────────────────────────────

def run_models():
    """List all available model aliases."""
    from providers.registry import MODEL_REGISTRY

    table = Table(title="Available Models")
    table.add_column("Alias", style="cyan bold")
    table.add_column("Model", style="white")
    table.add_column("Provider", style="yellow")
    table.add_column("Description", style="dim")

    for alias, entry in MODEL_REGISTRY.items():
        table.add_row(alias, entry.model_string, entry.provider_name, entry.description)

    console.print(table)


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

    table = Table(title="Recent Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Model", style="yellow")
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
        # Create defaults first
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
# run_update
# ──────────────────────────────────────────────

def run_update():
    console.print("[dim]Checking for updates...[/dim]")
    
    try:
        r = httpx.get(GITHUB_API, timeout=15, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        release = r.json()
    except Exception as e:
        console.print(f"[red]Could not reach GitHub: {e}[/red]")
        return

    latest_tag = release.get("tag_name", "").lstrip("v")
    html_url   = release.get("html_url", "")
    assets     = release.get("assets", [])

    if not latest_tag:
        console.print("[red]Could not read release version from GitHub.[/red]")
        return

    if _version_tuple(latest_tag) <= _version_tuple(CURRENT_VERSION):
        console.print(f"[green]✓ You're already on the latest version[/green] (v{CURRENT_VERSION})")
        return

    console.print(
        f"\n[bold yellow]Update available:[/bold yellow] "
        f"v{CURRENT_VERSION} → [bold green]v{latest_tag}[/bold green]"
    )

    asset_name, asset_url = _pick_asset(assets)

    if not asset_url:
        console.print(
            f"[yellow]No installer found for your OS in this release.[/yellow]\n"
            f"Download manually: [cyan]{html_url}[/cyan]"
        )
        return

    console.print(f"Downloading [bold]{asset_name}[/bold]...")

    try:
        tmp_path = _download_with_progress(asset_url, asset_name)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        return

    console.print(f"\n[bold]Installing v{latest_tag}...[/bold]")
    _run_installer(tmp_path, asset_name)

def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)

def _pick_asset(assets: list) -> tuple[str, str]:
    system = platform.system().lower()
    if system == "windows":
        keywords = ["windows", "setup", ".exe"]
    elif system == "darwin":
        keywords = [".dmg", "macos", "mac"]
    else:
        is_debian = _is_debian_based()
        keywords = [".deb"] if is_debian else [".appimage"]

    for asset in assets:
        name = asset.get("name", "").lower()
        url  = asset.get("browser_download_url", "")
        if any(kw in name for kw in keywords):
            return asset["name"], url

    if assets:
        return assets[0]["name"], assets[0].get("browser_download_url", "")
    return "", ""

def _is_debian_based() -> bool:
    try:
        return os.path.exists("/etc/debian_version") or os.path.exists("/etc/apt")
    except Exception:
        return False

def _download_with_progress(url: str, filename: str) -> str:
    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(filename, total=total or None)
            for chunk in response.iter_bytes(chunk_size=8192):
                tmp.write(chunk)
                progress.advance(task, len(chunk))
    tmp.close()
    return tmp.name

def _run_installer(path: str, name: str):
    system = platform.system().lower()
    if system == "windows":
        subprocess.Popen([path], shell=True)
        sys.exit(0)
    elif system == "darwin":
        subprocess.Popen(["open", path])
        sys.exit(0)
    else:
        subprocess.Popen(["sudo", "dpkg", "-i", path])
        sys.exit(0)