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

CURRENT_VERSION = "0.2.5"
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
    Update Elio in-place by downloading the latest installer from GitHub
    and running it silently — no wizard, no manual steps, auto-closes
    the current process and reinstalls immediately.

    Windows  : Elio-Setup.exe /VERYSILENT /NORESTART /CLOSEAPPLICATIONS
    macOS    : mounts DMG, copies binary, unmounts
    Linux    : sudo dpkg -i  (or replaces AppImage in-place)
    """
    console.print("[dim]Checking for updates...[/dim]")

    # 1. Fetch latest release info from GitHub
    try:
        r = httpx.get(
            GITHUB_API, timeout=15,
            headers={"Accept": "application/vnd.github+json"},
        )
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
        console.print(
            f"[green]✓ Already on the latest version[/green] (v{CURRENT_VERSION})"
        )
        return

    console.print(
        f"\n[bold yellow]Update available:[/bold yellow] "
        f"v{CURRENT_VERSION} → [bold green]v{latest_tag}[/bold green]\n"
    )

    # 2. Pick the right asset for this OS
    asset_name, asset_url = _pick_asset(assets)

    if not asset_url:
        console.print(
            f"[yellow]No installer found for your OS in this release.[/yellow]\n"
            f"Download manually: [cyan]{html_url}[/cyan]"
        )
        return

    # 3. Download with progress bar
    console.print(f"Downloading [bold]{asset_name}[/bold]...")
    try:
        tmp_path = _download_with_progress(asset_url, asset_name)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        return

    # 4. Run silently — the installer overwrites files in-place, no wizard shown
    console.print(f"\n[bold]Installing v{latest_tag} silently...[/bold]")
    _run_installer_silent(tmp_path, asset_name, latest_tag)


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)


def _pick_asset(assets: list) -> tuple[str, str]:
    system = platform.system().lower()
    if system == "windows":
        keywords = [".exe", "setup", "windows"]
    elif system == "darwin":
        keywords = [".dmg", "macos", "mac"]
    else:
        keywords = [".deb"] if _is_debian_based() else [".appimage"]

    for asset in assets:
        name = asset.get("name", "").lower()
        url  = asset.get("browser_download_url", "")
        if any(kw in name for kw in keywords):
            return asset["name"], url

    # Fallback to first asset
    if assets:
        return assets[0]["name"], assets[0].get("browser_download_url", "")
    return "", ""


def _is_debian_based() -> bool:
    return os.path.exists("/etc/debian_version") or os.path.exists("/etc/apt")


def _download_with_progress(url: str, filename: str) -> str:
    import tempfile
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn,
        DownloadColumn, TransferSpeedColumn, TextColumn,
    )
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


def _run_installer_silent(path: str, name: str, version: str):
    """
    Run the installer silently so it updates in-place with no user interaction.

    Inno Setup (Windows): /VERYSILENT /NORESTART /CLOSEAPPLICATIONS
      - Closes any running elio.exe automatically
      - Copies the new binary over the old one
      - No wizard, no clicks needed

    macOS DMG: mount → copy binary → unmount
    Linux .deb: sudo dpkg -i --force-overwrite
    Linux AppImage: replace the AppImage file in-place
    """
    system = platform.system().lower()

    if system == "windows":
        console.print("[dim]Running installer silently — Elio will restart automatically.[/dim]")
        # /VERYSILENT   — no UI at all
        # /NORESTART    — don't reboot after install
        # /CLOSEAPPLICATIONS — auto-close running elio.exe so file isn't locked
        subprocess.Popen(
            [path, "/VERYSILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
            shell=False,
        )
        console.print(f"\n[bold green]✓ Update to v{version} is installing now.[/bold green]")
        console.print("[dim]Elio will close. Open a new terminal to use the updated version.[/dim]\n")
        sys.exit(0)

    elif system == "darwin":
        # Mount the DMG, copy the binary, unmount
        import shutil
        console.print("[dim]Mounting disk image...[/dim]")
        try:
            mount_result = subprocess.run(
                ["hdiutil", "attach", "-nobrowse", "-quiet", path],
                capture_output=True, text=True, check=True,
            )
            # Find the mount point (last line of output)
            mount_point = mount_result.stdout.strip().split("\n")[-1].split("\t")[-1].strip()

            # Find the elio binary inside the DMG
            elio_in_dmg = None
            for candidate in [
                os.path.join(mount_point, "elio"),
                os.path.join(mount_point, "Elio", "elio"),
            ]:
                if os.path.exists(candidate):
                    elio_in_dmg = candidate
                    break

            if not elio_in_dmg:
                console.print(f"[red]Could not find elio binary in DMG at {mount_point}[/red]")
                subprocess.run(["hdiutil", "detach", mount_point, "-quiet"])
                return

            # Find where current elio is installed
            current_elio = shutil.which("elio") or "/usr/local/bin/elio"
            console.print(f"[dim]Copying new binary to {current_elio}...[/dim]")

            shutil.copy2(elio_in_dmg, current_elio)
            os.chmod(current_elio, 0o755)

            subprocess.run(["hdiutil", "detach", mount_point, "-quiet"])

            console.print(f"\n[bold green]✓ Updated to v{version}![/bold green]")
            console.print("[dim]Open a new terminal and run `elio` to use the updated version.[/dim]\n")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]macOS update failed: {e}[/red]")
            console.print(f"[dim]Install manually: open {path}[/dim]")

    else:
        # Linux
        if name.lower().endswith(".deb"):
            console.print("[dim]Installing .deb package (may ask for sudo password)...[/dim]")
            result = subprocess.run(
                ["sudo", "dpkg", "-i", "--force-overwrite", path],
            )
            if result.returncode == 0:
                console.print(f"\n[bold green]✓ Updated to v{version}![/bold green]")
                console.print("[dim]Open a new terminal and run `elio` to use the updated version.[/dim]\n")
            else:
                console.print(f"[red]dpkg install failed (exit {result.returncode}).[/red]")
        else:
            # AppImage — replace in-place
            import shutil
            current_elio = shutil.which("elio")
            if current_elio and os.path.isfile(current_elio):
                console.print(f"[dim]Replacing AppImage at {current_elio}...[/dim]")
                os.chmod(path, 0o755)
                shutil.move(path, current_elio)
                console.print(f"\n[bold green]✓ Updated to v{version}![/bold green]")
                console.print("[dim]Open a new terminal and run `elio` to use the updated version.[/dim]\n")
            else:
                console.print(
                    f"[yellow]Could not find current elio binary location.[/yellow]\n"
                    f"[dim]Run manually: chmod +x {path} && sudo mv {path} /usr/local/bin/elio[/dim]"
                )
