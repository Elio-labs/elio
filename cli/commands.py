import sys
import os
import platform
import subprocess
import tempfile
import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, DownloadColumn, TransferSpeedColumn, BarColumn, TextColumn
 
console = Console()
 
CURRENT_VERSION = "0.1.0"
GITHUB_API = "https://api.github.com/repos/Elio-labs/elio/releases/latest"
 
 
def run_update():
    """Check for a newer release and install it automatically."""
 
    console.print("[dim]Checking for updates...[/dim]")
 
    # ── 1. Fetch latest release info from GitHub ──
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
 
    # ── 2. Compare versions ──
    if _version_tuple(latest_tag) <= _version_tuple(CURRENT_VERSION):
        console.print(f"[green]✓ You're already on the latest version[/green] (v{CURRENT_VERSION})")
        return
 
    console.print(
        f"\n[bold yellow]Update available:[/bold yellow] "
        f"v{CURRENT_VERSION} → [bold green]v{latest_tag}[/bold green]"
    )
 
    # ── 3. Pick the right asset for this OS ──
    asset_name, asset_url = _pick_asset(assets)
 
    if not asset_url:
        console.print(
            f"[yellow]No installer found for your OS in this release.[/yellow]\n"
            f"Download manually: [cyan]{html_url}[/cyan]"
        )
        return
 
    console.print(f"Downloading [bold]{asset_name}[/bold]...")
 
    # ── 4. Download to a temp file ──
    try:
        tmp_path = _download_with_progress(asset_url, asset_name)
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")
        return
 
    # ── 5. Run the installer ──
    console.print(f"\n[bold]Installing v{latest_tag}...[/bold]")
    _run_installer(tmp_path, asset_name)
 
 
# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
 
def _version_tuple(v: str) -> tuple:
    """Turn '0.2.5' into (0, 2, 5) for safe comparison."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)
 
 
def _pick_asset(assets: list) -> tuple[str, str]:
    """
    Return (name, download_url) for the right installer based on the current OS.
 
    Asset naming convention in GitHub Releases:
      Windows  → Elio-Setup-Windows.exe
      macOS    → Elio-macOS.dmg
      Linux    → elio-linux.deb  (Debian/Ubuntu)   or  elio-linux.AppImage
    """
    system = platform.system().lower()
 
    # Priority keywords per OS
    if system == "windows":
        keywords = ["windows", "setup", ".exe"]
    elif system == "darwin":
        keywords = [".dmg", "macos", "mac"]
    else:
        # Linux — prefer .deb if available, fall back to AppImage
        is_debian = _is_debian_based()
        keywords = [".deb"] if is_debian else [".appimage"]
 
    for asset in assets:
        name = asset.get("name", "").lower()
        url  = asset.get("browser_download_url", "")
        if any(kw in name for kw in keywords):
            return asset["name"], url
 
    # Fallback: return first asset
    if assets:
        return assets[0]["name"], assets[0].get("browser_download_url", "")
    return "", ""
 
 
def _is_debian_based() -> bool:
    try:
        return os.path.exists("/etc/debian_version") or os.path.exists("/etc/apt")
    except Exception:
        return False
 
 
def _download_with_progress(url: str, filename: str) -> str:
    """Stream-download `url` into a temp file, show a progress bar. Returns the temp path."""
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
    """Launch the downloaded installer the right way for each OS."""
    system = platform.system().lower()