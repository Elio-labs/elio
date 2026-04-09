import typer
from typing import Optional
from elio.cli import app
import elio.cli.commands  # registers login/logout/status/config subcommands
import os
import sys
import shutil
import winreg
from pathlib import Path


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Start with a specific model alias"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
):
    """Elio — Unified AI CLI. Run without arguments to start chatting."""
    if version:
        typer.echo("elio 0.1.0")
        raise typer.Exit()

    # If a subcommand was invoked (login, status, etc.), don't open TUI
    if ctx.invoked_subcommand is not None:
        return

    # Check at least one provider is configured
    from elio.auth.manager import get_connected_providers
    if not get_connected_providers():
        typer.echo("No providers configured. Run `elio login` first.", err=True)
        raise typer.Exit(1)

    from elio.tui.app import run_tui
    run_tui(alias=model)

def setup_system_path():
    if os.name != 'nt':
        return

    home = Path.home()
    bin_dir = home / '.elio' / 'bin'
    bin_dir.mkdir(parents=True, exist_ok=True)

    current_exe = Path(sys.executable)
    target_exe = bin_dir / 'elio.exe'

    if current_exe.parent != bin_dir:
        try:
            shutil.copy(current_exe, target_exe)
        except Exception:
            pass

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        current_path, _ = winreg.QueryValueEx(key, "Path")

        if str(bin_dir) not in current_path:
            new_path = f"{current_path};{str(bin_dir)}"
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
    except Exception:
        pass


if __name__ == "__main__":
    setup_system_path()
    app()