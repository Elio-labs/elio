from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tui.app import ElioApp


@dataclass
class CommandResult:
    output: str       # text to display in the chat log
    error: bool = False


HELP_TEXT = """
[bold]Available slash commands:[/bold]

  /model [alias]    Switch active model (aliases: claude, fast, gpt, gemini, coding, writing, research, vision)
  /clear            Clear conversation context and screen
  /history          List recent sessions
  /load [id]        Load a previous session by ID
  /export           Save current session as Markdown to ~/elio-exports/
  /tokens           Show current context token usage estimate
  /status           Show auth status for all providers
  /attach [path]    Attach a file to the next message
  /help             Show this help text
"""


async def route_command(cmd: str, app: "ElioApp") -> CommandResult:
    """
    Parse a slash command string and perform the action.
    Returns a CommandResult with text to display in the log.
    """
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # /help
    if name == "/help":
        return CommandResult(HELP_TEXT)

    # /model [alias]
    if name == "/model":
        if not arg:
            return CommandResult(f"[yellow]Current model: {app.current_alias}[/yellow]")
        try:
            from providers.registry import resolve_model
            entry = resolve_model(arg)
            app.current_alias = arg
            app.title = f"Elio — {arg}"
            return CommandResult(f"[green]→ Switched to {entry.model_string}[/green]")
        except KeyError as e:
            return CommandResult(f"[red]{e}[/red]", error=True)

    # /clear
    if name == "/clear":
        app.history = []
        await app.action_clear_chat()
        return CommandResult("[dim]Context cleared.[/dim]")

    # /history
    if name == "/history":
        sessions = app.session_manager.recent_sessions()
        if not sessions:
            return CommandResult("[dim]No sessions found.[/dim]")
        lines = ["[bold]Recent sessions:[/bold]"]
        for s in sessions:
            lines.append(f"  [cyan]{s['id']}[/cyan]  {s['title']}  [dim]{s['updated'][:16]}[/dim]")
        return CommandResult("\n".join(lines))

    # /load [session_id]
    if name == "/load":
        if not arg:
            return CommandResult("[red]Usage: /load [session_id][/red]", error=True)
        try:
            messages = app.session_manager.load(arg)
            app.history = messages
            return CommandResult(f"[green]Loaded session {arg} ({len(messages)} messages).[/green]")
        except Exception as e:
            return CommandResult(f"[red]Failed to load: {e}[/red]", error=True)

    # /export
    if name == "/export":
        if not app.history:
            return CommandResult("[yellow]Nothing to export.[/yellow]")
        path = app.session_manager.export_markdown(
            app.history, export_dir=app.config.export_dir
        )
        return CommandResult(f"[green]Exported to {path}[/green]")

    # /tokens
    if name == "/tokens":
        total_chars = sum(len(m.content) for m in app.history)
        estimated = total_chars // 4
        limit = app.config.max_context_tokens
        return CommandResult(
            f"[cyan]~{estimated:,} / {limit:,} tokens used ({100*estimated//limit}%)[/cyan]"
        )

    # /status
    if name == "/status":
        from auth.manager import get_connected_providers
        connected = get_connected_providers()
        return CommandResult("Connected: " + ", ".join(connected) if connected else "No providers connected.")

    # /attach [path]
    if name == "/attach":
        if not arg:
            return CommandResult("[red]Usage: /attach /path/to/file[/red]", error=True)
        try:
            from files.handler import load_file
            attachment = load_file(arg)
            app.attached_files.append(attachment)
            return CommandResult(
                f"[green]Attached: {attachment.name} ({attachment.mime_type})[/green]"
            )
        except (FileNotFoundError, ValueError) as e:
            return CommandResult(f"[red]{e}[/red]", error=True)

    return CommandResult(f"[red]Unknown command: {name}. Type /help for commands.[/red]", error=True)