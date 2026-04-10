"""
Elio CLI — Inline chat interface.

This is the core of Elio: a Rich + prompt_toolkit inline terminal chat loop
that lives directly in the user's terminal (no separate window).
Inspired by Claude Code / Aider.
"""

import asyncio
import os
import sys
import signal
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
from rich.prompt import Prompt, IntPrompt
from rich.rule import Rule
from rich.live import Live
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

VERSION = "0.2.0"

# ── Prompt toolkit styling ──────────────────────────────────────────────────

PT_STYLE = PTStyle.from_dict({
    "prompt": "#6c71c4 bold",
    "": "#93a1a1",
})

# ── Branding ────────────────────────────────────────────────────────────────

LOGO = """[bold #6c71c4]
  ████████ ██       ██  ██████
  ██       ██       ██ ██    ██
  ██████   ██       ██ ██    ██
  ██       ██       ██ ██    ██
  ████████ ████████ ██  ██████[/bold #6c71c4]"""


def _tier_badge(is_free: bool) -> str:
    return "[bold green]FREE[/bold green]" if is_free else "[bold yellow]PAID[/bold yellow]"


def _provider_badge(provider_key: str) -> str:
    info = PROVIDERS[provider_key]
    if info.has_free:
        return f"[green]*[/green] {info.name} ({info.brand})"
    return f"[yellow]*[/yellow] {info.name} ({info.brand})"


# ── Provider & Model Selection ──────────────────────────────────────────────

def select_provider(current_provider: str | None = None) -> str | None:
    """Interactive provider selector. Returns provider key or None if cancelled."""
    console.print()
    console.print("[bold]Select AI Provider:[/bold]")
    console.print()

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info = PROVIDERS[key]
        free_tag = "  [dim green]· free tier available[/dim green]" if info.has_free else "  [dim]· API key required[/dim]"
        marker = " [cyan]<[/cyan]" if key == current_provider else ""
        console.print(f"    [bold]{i}.[/bold] {_provider_badge(key)}{free_tag}{marker}")

    console.print()
    try:
        choice = IntPrompt.ask(
            "  Choice",
            default=PROVIDER_ORDER.index(current_provider) + 1 if current_provider in PROVIDER_ORDER else 1,
        )
        if 1 <= choice <= len(PROVIDER_ORDER):
            return PROVIDER_ORDER[choice - 1]
        console.print("[red]  Invalid choice.[/red]")
        return None
    except (KeyboardInterrupt, EOFError):
        return None


def select_model(provider_key: str, current_alias: str | None = None) -> str | None:
    """Interactive model selector for a given provider. Returns alias or None."""
    models = get_models_for_provider(provider_key)
    info = PROVIDERS[provider_key]

    console.print()
    console.print(f"[bold]Select Model ({info.name}):[/bold]")
    console.print()

    # Table header
    console.print(f"    [dim]{'#':>3}  {'Model':<24} {'Tier':<8} Description[/dim]")
    console.print(f"    [dim]{'─'*3}  {'─'*24} {'─'*8} {'─'*30}[/dim]")

    for i, m in enumerate(models, 1):
        tier = "[green]Free[/green] " if m.is_free else "[yellow]Paid[/yellow] "
        marker = " [cyan]<[/cyan]" if m.alias == current_alias else ""
        console.print(f"    [bold]{i:>3}.[/bold] {m.display_name:<24} {tier}  {m.description}{marker}")

    console.print()

    # Determine default: current model if in this provider, else 1
    default_idx = 1
    for i, m in enumerate(models, 1):
        if m.alias == current_alias:
            default_idx = i
            break

    try:
        choice = IntPrompt.ask("  Choice", default=default_idx)
        if 1 <= choice <= len(models):
            selected = models[choice - 1]
            # Check if user has the API key for paid models
            key = get_api_key(provider_key)
            if not key:
                console.print(
                    f"\n  [yellow]! No API key for {info.name}.[/yellow] "
                    f"Run [bold cyan]elio login {provider_key}[/bold cyan] first.\n"
                )
                return None
            return selected.alias
        console.print("[red]  Invalid choice.[/red]")
        return None
    except (KeyboardInterrupt, EOFError):
        return None


def full_provider_model_select(current_provider: str | None = None, current_alias: str | None = None) -> tuple[str, str] | None:
    """Full two-level selection: provider → model. Returns (provider, alias) or None."""
    provider = select_provider(current_provider)
    if not provider:
        return None

    alias = select_model(provider, current_alias if current_provider == provider else None)
    if not alias:
        return None

    return provider, alias


# ── Startup Banner ──────────────────────────────────────────────────────────

def print_banner(provider_key: str, model_alias: str):
    """Print the gorgeous startup banner."""
    entry = resolve_model(model_alias)
    info = PROVIDERS[provider_key]
    tier = "free" if entry.is_free else "paid"

    banner_content = (
        f"{LOGO}\n"
        f"[dim]   Unified AI Coding Agent · v{VERSION}[/dim]\n"
        f"   Provider: [bold]{info.name}[/bold] · {entry.display_name} [dim]({tier})[/dim]\n"
        f"\n"
        f"   [dim]/help for commands · /provider to switch AI[/dim]"
    )

    console.print(Panel(
        banner_content,
        border_style="#6c71c4",
        padding=(0, 1),
    ))
    console.print()


# ── Build prompt text ───────────────────────────────────────────────────────

def make_prompt_text(provider_key: str, model_alias: str) -> HTML:
    """Build the prompt_toolkit prompt showing current provider/model."""
    entry = resolve_model(model_alias)
    return HTML(
        f'<style fg="#6c71c4">[{provider_key} > {entry.display_name}]</style> '
        f'<style fg="#6c71c4"><b>elio ></b></style> '
    )


# ── Main Chat Loop ─────────────────────────────────────────────────────────

def run_chat(
    provider_override: str | None = None,
    model_override: str | None = None,
):
    """
    Main entry point for the Elio inline chat.
    Called by `elio` (no subcommand) or `elio chat`.
    """
    config = load_config()

    # Determine initial provider and model
    current_provider = provider_override or config.default_provider
    current_alias = model_override or config.default_model

    # Validate the provider/model combo
    if current_provider not in PROVIDERS:
        current_provider = "google"
    if current_alias not in MODEL_REGISTRY:
        current_alias = get_default_model_for_provider(current_provider).alias

    # Make sure the model belongs to the selected provider
    entry = resolve_model(current_alias)
    if entry.provider_name != current_provider:
        current_alias = get_default_model_for_provider(current_provider).alias

    # Print the banner
    print_banner(current_provider, current_alias)

    # Setup prompt_toolkit session with persistent history
    history_path = Path.home() / ".elio" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
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
            session=session,
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

                # Print output
                if result.output:
                    console.print(result.output)

                # Handle state changes from commands
                if result.new_provider:
                    current_provider = result.new_provider
                if result.new_alias:
                    current_alias = result.new_alias
                    session_manager.start_new(current_alias)
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
            # Ctrl+C during input — just show a new prompt
            console.print()
            continue
        except EOFError:
            # Ctrl+D — exit
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

    # Show AI header
    console.print(f"\n[bold #6c71c4]{entry.display_name}:[/bold #6c71c4]")

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

        # End the response block
        console.print("\n")

        # Save assistant response
        history.append(Message(role="assistant", content=full_response))
        session_manager.save_turn("assistant", full_response)

        # Clear attached files after sending
        attached_files.clear()

    except Exception as e:
        error_msg = friendly_error(e)
        console.print(f"\n{error_msg}\n")
