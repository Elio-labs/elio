"""
Elio CLI — Inline chat interface.

Rich + prompt_toolkit inline terminal chat with a "Select your AI"
selector on every launch. No hardcoded default model.
"""

import asyncio
import os
import sys
from typing import Optional

# Fix Windows console encoding — must run before any Rich output
if sys.platform == "win32":
    os.system("")  # enable ANSI on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich.rule import Rule
from rich.live import Live
from rich.columns import Columns
from rich.align import Align
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML
from pathlib import Path

from providers.registry import (
    MODEL_REGISTRY, PROVIDERS, PROVIDER_ORDER, PROVIDER_MODELS,
    resolve_model, get_provider, get_models_for_provider,
    get_default_model_for_provider, ModelEntry,
)
from providers.base import Message
from config.loader import load_config, save_config
from session.manager import SessionManager
from auth.manager import get_api_key, get_connected_providers
from utils.error import friendly_error

console = Console()

VERSION = "0.2.5"

# ── Prompt toolkit styling ──────────────────────────────────────────────────

PT_STYLE = PTStyle.from_dict({
    "prompt": "#6c71c4 bold",
    "": "#93a1a1",
})

# ── ASCII Logo ───────────────────────────────────────────────────────────────

LOGO = """\
[bold #6c71c4]  ████████ ██       ██  ██████
  ██       ██       ██ ██    ██
  ██████   ██       ██ ██    ██
  ██       ██       ██ ██    ██
  ████████ ████████ ██  ██████[/bold #6c71c4]"""


# ── Startup Banner ──────────────────────────────────────────────────────────

def print_welcome_banner():
    """Print the Elio welcome banner (before model selection)."""
    console.print()
    console.print(Panel(
        f"{LOGO}\n\n"
        f"[dim]  Unified AI in your terminal · v{VERSION}[/dim]\n"
        f"  [dim]Claude · Gemini · ChatGPT — one command[/dim]",
        border_style="#6c71c4",
        padding=(0, 2),
    ))
    console.print()


def print_chat_banner(provider_key: str, model_alias: str):
    """Print banner after model is selected, shown above the chat."""
    entry = resolve_model(model_alias)
    info = PROVIDERS[provider_key]
    tier = "[green]free[/green]" if entry.is_free else "[yellow]paid[/yellow]"
    console.print(Panel(
        f"[bold #6c71c4]{info.name}[/bold #6c71c4] · [bold]{entry.display_name}[/bold] · {tier}\n"
        f"[dim]  /help for commands  ·  /provider to switch AI  ·  /exit to quit[/dim]",
        border_style="#6c71c4",
        padding=(0, 1),
    ))
    console.print()


# ── Provider / Model Selection ──────────────────────────────────────────────

def select_ai() -> tuple[str, str] | None:
    """
    Show the 'Select your AI' screen.
    Returns (provider_key, model_alias) or None if cancelled.
    """
    console.print(Rule("[bold #6c71c4]  🤖  SELECT YOUR AI  [/bold #6c71c4]", style="#6c71c4"))
    console.print()

    # Build provider table
    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column("Num",    style="bold #6c71c4", width=4, no_wrap=True)
    table.add_column("Name",   style="bold white",   width=14, no_wrap=True)
    table.add_column("Brand",  style="cyan",          width=10, no_wrap=True)
    table.add_column("Free",   width=8,  no_wrap=True)
    table.add_column("Best for", style="dim",         width=28, no_wrap=True)

    best_for = {
        "google":    "Research, summarization, coding",
        "anthropic": "Coding, debugging, reasoning",
        "openai":    "Writing, creativity, chat",
    }

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info = PROVIDERS[key]
        free_tag = "[green]✓ Free[/green]" if info.has_free else "[dim]API key[/dim]"
        # Show connected status
        has_key = get_api_key(key) is not None
        connected = "[dim green] ●[/dim green]" if has_key else "[dim red] ○[/dim red]"
        table.add_row(
            f"{i}.",
            f"{info.name}{connected}",
            info.brand,
            free_tag,
            best_for.get(key, ""),
        )

    console.print(table)
    console.print()
    console.print("[dim]  ● = API key configured   ○ = not configured[/dim]")
    console.print()

    # Get provider choice
    try:
        raw = input("  Enter 1–3 to select provider: ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled.[/dim]")
        return None

    if not raw.isdigit() or not (1 <= int(raw) <= len(PROVIDER_ORDER)):
        console.print("[red]  Invalid choice.[/red]")
        return None

    provider_key = PROVIDER_ORDER[int(raw) - 1]
    info = PROVIDERS[provider_key]

    # Check if API key is configured
    if not get_api_key(provider_key):
        console.print()
        console.print(f"  [yellow]! No API key for {info.name}.[/yellow]")
        console.print(f"  [dim]Run [bold cyan]elio login[/bold cyan] to add your key, or choose a different provider.[/dim]")
        console.print()
        try:
            add_now = input("  Add API key now? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None
        if add_now == "y":
            from auth.manager import set_api_key
            try:
                import getpass
                key_val = getpass.getpass(f"  Paste your {info.name} API key: ").strip()
            except (KeyboardInterrupt, EOFError):
                return None
            if key_val:
                set_api_key(provider_key, key_val)
                console.print(f"  [green]✓ {info.name} key saved.[/green]")
            else:
                console.print("  [dim]Skipped — no key entered.[/dim]")
                return None
        else:
            return None

    # Now select a model
    console.print()
    alias = select_model(provider_key, current_alias=None)
    if not alias:
        return None

    return provider_key, alias


def select_provider(current_provider: str | None = None) -> str | None:
    """Interactive provider selector. Returns provider key or None if cancelled."""
    console.print()
    console.print(Rule("[bold #6c71c4]  Switch AI Provider  [/bold #6c71c4]", style="#6c71c4"))
    console.print()

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info = PROVIDERS[key]
        has_key = get_api_key(key) is not None
        free_tag = "  [dim green]· free tier[/dim green]" if info.has_free else "  [dim]· API key required[/dim]"
        connected = "[green] ●[/green]" if has_key else "[red] ○[/red]"
        marker = "  [cyan]◀ current[/cyan]" if key == current_provider else ""
        console.print(f"    [bold #6c71c4]{i}.[/bold #6c71c4]  {info.name}{connected} ({info.brand}){free_tag}{marker}")

    console.print()
    try:
        raw = input("  Choice [1-3]: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw.isdigit() or not (1 <= int(raw) <= len(PROVIDER_ORDER)):
        console.print("[red]  Invalid choice.[/red]")
        return None

    chosen = PROVIDER_ORDER[int(raw) - 1]

    # Check key
    if not get_api_key(chosen):
        info = PROVIDERS[chosen]
        console.print(f"\n  [yellow]! No API key for {info.name}.[/yellow]")
        console.print(f"  Run [bold cyan]elio login {chosen}[/bold cyan] first.\n")
        return None

    return chosen


def select_model(provider_key: str, current_alias: str | None = None) -> str | None:
    """Interactive model selector for a given provider. Returns alias or None."""
    models = get_models_for_provider(provider_key)
    info = PROVIDERS[provider_key]

    console.print()
    console.print(f"  [bold]Select model — {info.name} ({info.brand}):[/bold]")
    console.print()

    for i, m in enumerate(models, 1):
        tier = "[green]Free [/green]" if m.is_free else "[yellow]Paid [/yellow]"
        marker = "  [cyan]◀[/cyan]" if m.alias == current_alias else ""
        console.print(f"    [bold #6c71c4]{i:>2}.[/bold #6c71c4]  {m.display_name:<28} {tier}  [dim]{m.description}[/dim]{marker}")

    console.print()

    # Default = current model or first
    default_idx = 1
    for i, m in enumerate(models, 1):
        if m.alias == current_alias:
            default_idx = i
            break

    try:
        raw = input(f"  Choice [1-{len(models)}] (default {default_idx}): ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw:
        raw = str(default_idx)

    if not raw.isdigit() or not (1 <= int(raw) <= len(models)):
        console.print("[red]  Invalid choice.[/red]")
        return None

    selected = models[int(raw) - 1]
    return selected.alias


def full_provider_model_select(
    current_provider: str | None = None,
    current_alias: str | None = None,
) -> tuple[str, str] | None:
    """Two-level selection: provider → model. Returns (provider, alias) or None."""
    provider = select_provider(current_provider)
    if not provider:
        return None

    alias = select_model(provider, current_alias if current_provider == provider else None)
    if not alias:
        return None

    return provider, alias


# ── Build prompt text ───────────────────────────────────────────────────────

def make_prompt_text(provider_key: str, model_alias: str) -> HTML:
    """Build the prompt_toolkit prompt showing current provider/model."""
    entry = resolve_model(model_alias)
    return HTML(
        f'<style fg="#6c71c4">[{entry.display_name}]</style> '
        f'<style fg="#6c71c4"><b>❯</b></style> '
    )


# ── Main Chat Entry Point ───────────────────────────────────────────────────

def run_chat(
    provider_override: str | None = None,
    model_override: str | None = None,
):
    """
    Main entry point for the Elio inline chat.
    Called by `elio` (no subcommand).

    Always shows the "Select your AI" selector — no hardcoded defaults.
    """
    config = load_config()

    # Show welcome banner first
    print_welcome_banner()

    # If provider/model passed on CLI, use those directly
    if provider_override and model_override:
        current_provider = provider_override
        current_alias = model_override
    else:
        # Always show the selector — this is the core UX
        result = select_ai()
        if not result:
            console.print("\n[dim]No model selected. Exiting.[/dim]\n")
            return
        current_provider, current_alias = result

    # Clear screen and show chat banner
    os.system("cls" if os.name == "nt" else "clear")
    print_chat_banner(current_provider, current_alias)

    # Setup prompt_toolkit session with persistent history
    history_path = Path.home() / ".elio" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    pt_session = PromptSession(
        history=FileHistory(str(history_path)),
        style=PT_STYLE,
        multiline=False,
        enable_history_search=True,
    )

    # Session manager for saving conversations
    session_manager = SessionManager()
    session_manager.start_new(current_alias)

    # Conversation history
    history: list[Message] = []
    attached_files = []

    # Run the async event loop
    try:
        asyncio.run(_chat_loop(
            session=pt_session,
            session_manager=session_manager,
            history=history,
            attached_files=attached_files,
            current_provider=current_provider,
            current_alias=current_alias,
            config=config,
        ))
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye! 👋[/dim]")
    except EOFError:
        console.print("\n[dim]Goodbye! 👋[/dim]")


async def _chat_loop(
    session: PromptSession,
    session_manager: SessionManager,
    history: list[Message],
    attached_files: list,
    current_provider: str,
    current_alias: str,
    config,
):
    """The async main loop — reads input, processes commands, sends messages."""
    from cli.commands_router import route_command, CommandResult

    while True:
        try:
            # Build prompt
            prompt = make_prompt_text(current_provider, current_alias)

            # Get user input (run prompt_toolkit in executor to not block asyncio)
            text = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt(prompt, style=PT_STYLE),
            )
            text = text.strip()

            if not text:
                continue

            # ── Slash commands ──────────────────────────────────────────
            if text.startswith("/"):
                result = await route_command(
                    cmd=text,
                    history=history,
                    attached_files=attached_files,
                    current_provider=current_provider,
                    current_alias=current_alias,
                    session_manager=session_manager,
                    config=config,
                )

                if result.output:
                    console.print(result.output)

                if result.new_provider:
                    current_provider = result.new_provider
                if result.new_alias:
                    current_alias = result.new_alias
                    session_manager.start_new(current_alias)
                    # Show updated banner
                    print_chat_banner(current_provider, current_alias)
                if result.clear_history:
                    history.clear()
                    attached_files.clear()
                if result.should_exit:
                    console.print("[dim]Goodbye! 👋[/dim]")
                    return

                continue

            # ── Send message to AI ──────────────────────────────────────
            await _send_message(
                text=text,
                history=history,
                attached_files=attached_files,
                current_alias=current_alias,
                current_provider=current_provider,
                session_manager=session_manager,
            )

        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            console.print("\n[dim]Goodbye! 👋[/dim]")
            return


async def _send_message(
    text: str,
    history: list[Message],
    attached_files: list,
    current_alias: str,
    current_provider: str,
    session_manager: SessionManager,
):
    """Send a message to the AI and stream the response inline."""
    entry = resolve_model(current_alias)

    # Show user message
    console.print(f"\n[bold green]You:[/bold green] {text}")

    # Add to history
    history.append(Message(role="user", content=text))
    session_manager.save_turn("user", text)

    # Show AI label
    console.print(f"\n[bold #6c71c4]{entry.display_name}:[/bold #6c71c4] ", end="")

    try:
        provider = get_provider(current_alias)
        full_response = ""

        # Stream tokens directly to console
        async for token in provider.stream_chat(
            messages=history,
            model=entry.model_string,
            files=attached_files or None,
        ):
            console.print(token, end="", highlight=False)
            full_response += token

        console.print("\n")

        # Save assistant response
        history.append(Message(role="assistant", content=full_response))
        session_manager.save_turn("assistant", full_response)

        # Clear attached files after sending
        attached_files.clear()

    except Exception as e:
        error_msg = friendly_error(e)
        console.print(f"\n{error_msg}\n")
