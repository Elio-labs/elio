"""
Elio CLI — Inline chat interface.
Starts with "Select your AI" — no hardcoded defaults.
"""

import asyncio
import os
import sys
from typing import Optional

if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML
from pathlib import Path

from providers.registry import (
    MODEL_REGISTRY, PROVIDERS, PROVIDER_ORDER, PROVIDER_MODELS,
    resolve_model, get_provider, get_models_for_provider,
    get_default_model_for_provider,
)
from providers.base import Message
from config.loader import load_config, save_config
from session.manager import SessionManager
from auth.manager import get_api_key, is_provider_ready
from utils.error import friendly_error

console = Console()
VERSION = "0.2.5"

PT_STYLE = PTStyle.from_dict({
    "prompt": "#6c71c4 bold",
    "":       "#93a1a1",
})

LOGO = """\
[bold #6c71c4]  ████████ ██       ██  ██████
  ██       ██       ██ ██    ██
  ██████   ██       ██ ██    ██
  ██       ██       ██ ██    ██
  ████████ ████████ ██  ██████[/bold #6c71c4]"""


# ── Banners ─────────────────────────────────────────────────────────────────

def print_welcome_banner():
    console.print()
    console.print(Panel(
        f"{LOGO}\n\n"
        f"[dim]  Unified AI in your terminal · v{VERSION}[/dim]\n"
        f"  [dim]Groq · Gemini · Claude · GPT — one command[/dim]",
        border_style="#6c71c4",
        padding=(0, 2),
    ))
    console.print()


def print_chat_banner(provider_key: str, model_alias: str):
    entry = resolve_model(model_alias)
    info  = PROVIDERS[provider_key]
    tier  = "[green]free[/green]" if entry.is_free else "[yellow]paid[/yellow]"
    console.print(Panel(
        f"[bold #6c71c4]{info.name}[/bold #6c71c4] · [bold]{entry.display_name}[/bold] · {tier}\n"
        f"[dim]  /help for commands · /provider to switch AI · /exit to quit[/dim]",
        border_style="#6c71c4",
        padding=(0, 1),
    ))
    console.print()


# ── Provider / Model Selection ───────────────────────────────────────────────

def _login_label(provider_key: str) -> str:
    """Return a human-readable login method label for a provider."""
    info = PROVIDERS[provider_key]
    if info.login_method == "oauth_or_key":
        return "[green]Sign in with Google  or  free API key[/green]"
    elif info.login_method == "api_key":
        return "[green]Free API key (console.groq.com)[/green]"
    else:
        return "[yellow]Paid API key required[/yellow]"


def select_ai() -> tuple[str, str] | None:
    """
    'Select your AI' startup screen.
    Returns (provider_key, model_alias) or None if cancelled.
    """
    console.print(Rule("[bold #6c71c4]  SELECT YOUR AI  [/bold #6c71c4]", style="#6c71c4"))
    console.print()

    # Provider table
    table = Table(box=None, padding=(0, 2), show_header=True, header_style="dim")
    table.add_column("#",        style="bold #6c71c4", width=3,  no_wrap=True)
    table.add_column("Provider", style="bold white",   width=12, no_wrap=True)
    table.add_column("Models",   style="cyan",          width=22, no_wrap=True)
    table.add_column("Access",                          width=38, no_wrap=True)
    table.add_column("",                                width=3,  no_wrap=True)

    brand_models = {
        "groq":      "Llama 3.3, llama-3.1",
        "google":    "Gemini Fast / Thinking / Pro",
        "anthropic": "Claude Sonnet / Haiku",
        "openai":    "GPT-4o, GPT-4.1",
    }

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info    = PROVIDERS[key]
        ready   = is_provider_ready(key)
        status  = "[green]●[/green]" if ready else "[dim]○[/dim]"
        access  = _login_label(key)
        table.add_row(f"{i}.", info.name, brand_models[key], access, status)

    console.print(table)
    console.print()
    console.print("  [dim]● = ready to use    ○ = needs setup[/dim]")
    console.print()

    try:
        raw = input("  Enter 1–4 to select: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw.isdigit() or not (1 <= int(raw) <= len(PROVIDER_ORDER)):
        console.print("[red]  Invalid choice.[/red]")
        return None

    provider_key = PROVIDER_ORDER[int(raw) - 1]

    # Setup if not ready
    if not is_provider_ready(provider_key):
        ok = _setup_provider(provider_key)
        if not ok:
            return None

    # Select model
    console.print()
    alias = select_model(provider_key)
    if not alias:
        return None

    return provider_key, alias


def _setup_provider(provider_key: str) -> bool:
    """
    Guide the user through setting up a provider that isn't configured yet.
    Returns True if setup succeeded.
    """
    info = PROVIDERS[provider_key]
    console.print()

    if provider_key == "groq":
        console.print(f"  [bold]Set up Groq (FREE)[/bold]")
        console.print(f"  [dim]1. Go to: [cyan]console.groq.com[/cyan][/dim]")
        console.print(f"  [dim]2. Sign up (free) → API Keys → Create API Key[/dim]")
        console.print(f"  [dim]3. Paste your key below[/dim]")
        console.print()
        return _prompt_api_key("groq")

    elif provider_key == "google":
        console.print(f"  [bold]Set up Google Gemini[/bold]")
        console.print()
        console.print(f"  [bold #6c71c4]1.[/bold #6c71c4]  [bold]Sign in with Google[/bold]  [green](recommended — no key needed)[/green]")
        console.print(f"      Opens browser → log in with Google account → done")
        console.print()
        console.print(f"  [bold #6c71c4]2.[/bold #6c71c4]  [bold]Use a free API key[/bold]")
        console.print(f"      Get it free at: [cyan]aistudio.google.com[/cyan]")
        console.print()
        try:
            choice = input("  Enter 1 or 2: ").strip()
        except (KeyboardInterrupt, EOFError):
            return False

        if choice == "1":
            from auth.oauth import google_login
            return google_login()
        else:
            return _prompt_api_key("google")

    elif provider_key == "anthropic":
        console.print(f"  [bold]Set up Anthropic Claude[/bold]  [yellow](paid — requires credits)[/yellow]")
        console.print(f"  [dim]Get API key at: [cyan]console.anthropic.com[/cyan] → Settings → API Keys[/dim]")
        console.print(f"  [dim]Key starts with: sk-ant-...[/dim]")
        console.print()
        return _prompt_api_key("anthropic")

    elif provider_key == "openai":
        console.print(f"  [bold]Set up OpenAI GPT[/bold]  [yellow](paid — requires credits)[/yellow]")
        console.print(f"  [dim]Get API key at: [cyan]platform.openai.com[/cyan] → API Keys[/dim]")
        console.print(f"  [dim]Key starts with: sk-...[/dim]")
        console.print()
        return _prompt_api_key("openai")

    return False


def _prompt_api_key(provider: str) -> bool:
    """Ask user to paste an API key and save it. Returns True if saved."""
    import getpass
    from auth.manager import set_api_key
    try:
        key = getpass.getpass(f"  Paste API key: ").strip()
    except (KeyboardInterrupt, EOFError):
        return False
    if not key:
        console.print("  [dim]No key entered.[/dim]")
        return False
    set_api_key(provider, key)
    console.print(f"  [green]✓ Key saved.[/green]")
    return True


def select_provider(current_provider: str | None = None) -> str | None:
    """Switch-provider selector (used inside /provider command)."""
    console.print()
    console.print(Rule("[bold #6c71c4]  Switch AI Provider  [/bold #6c71c4]", style="#6c71c4"))
    console.print()

    for i, key in enumerate(PROVIDER_ORDER, 1):
        info  = PROVIDERS[key]
        ready = is_provider_ready(key)
        marker   = "  [cyan]◀ current[/cyan]" if key == current_provider else ""
        status   = "[green]●[/green]" if ready else "[dim]○[/dim]"
        free_tag = "  [green]FREE[/green]" if info.has_free else "  [yellow]PAID[/yellow]"
        console.print(f"    [bold #6c71c4]{i}.[/bold #6c71c4]  {status} {info.name} ({info.brand}){free_tag}{marker}")

    console.print()
    try:
        raw = input("  Choice [1-4]: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw.isdigit() or not (1 <= int(raw) <= len(PROVIDER_ORDER)):
        return None

    chosen = PROVIDER_ORDER[int(raw) - 1]
    if not is_provider_ready(chosen):
        ok = _setup_provider(chosen)
        if not ok:
            return None
    return chosen


def select_model(provider_key: str, current_alias: str | None = None) -> str | None:
    """Model selector for a given provider."""
    models = get_models_for_provider(provider_key)
    info   = PROVIDERS[provider_key]

    console.print(f"  [bold]Select model — {info.name} ({info.brand}):[/bold]")
    console.print()

    for i, m in enumerate(models, 1):
        tier   = "[green]FREE[/green] " if m.is_free else "[yellow]PAID[/yellow] "
        marker = "  [cyan]◀[/cyan]"     if m.alias == current_alias else ""
        console.print(f"    [bold #6c71c4]{i:>2}.[/bold #6c71c4]  {m.display_name:<28} {tier}  [dim]{m.description}[/dim]{marker}")

    console.print()

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

    return models[int(raw) - 1].alias


def full_provider_model_select(
    current_provider: str | None = None,
    current_alias: str | None = None,
) -> tuple[str, str] | None:
    provider = select_provider(current_provider)
    if not provider:
        return None
    alias = select_model(provider, current_alias if current_provider == provider else None)
    if not alias:
        return None
    return provider, alias


# ── Prompt ───────────────────────────────────────────────────────────────────

def make_prompt_text(provider_key: str, model_alias: str) -> HTML:
    entry = resolve_model(model_alias)
    return HTML(
        f'<style fg="#6c71c4">[{entry.display_name}]</style> '
        f'<style fg="#6c71c4"><b>❯</b></style> '
    )


# ── Main entry point ─────────────────────────────────────────────────────────

def run_chat(
    provider_override: str | None = None,
    model_override:    str | None = None,
):
    config = load_config()

    print_welcome_banner()

    if provider_override and model_override:
        current_provider = provider_override
        current_alias    = model_override
    else:
        result = select_ai()
        if not result:
            console.print("\n[dim]No model selected. Exiting.[/dim]\n")
            return
        current_provider, current_alias = result

    os.system("cls" if os.name == "nt" else "clear")
    print_chat_banner(current_provider, current_alias)

    history_path = Path.home() / ".elio" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    pt_session = PromptSession(
        history=FileHistory(str(history_path)),
        style=PT_STYLE,
        multiline=False,
        enable_history_search=True,
    )

    session_manager = SessionManager()
    session_manager.start_new(current_alias)

    history: list[Message] = []
    attached_files = []

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
        console.print("\n[dim]Goodbye! [/dim]")
    except EOFError:
        console.print("\n[dim]Goodbye! [/dim]")


async def _chat_loop(
    session, session_manager, history, attached_files,
    current_provider, current_alias, config,
):
    from cli.commands_router import route_command

    while True:
        try:
            prompt = make_prompt_text(current_provider, current_alias)
            text = await session.prompt_async(prompt, style=PT_STYLE)
            text = text.strip()
            if not text:
                continue

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
                    print_chat_banner(current_provider, current_alias)
                if result.clear_history:
                    history.clear()
                    attached_files.clear()
                if result.should_exit:
                    console.print("[dim]Goodbye![/dim]")
                    return
                continue

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
            console.print("\n[dim]Goodbye![/dim]")
            return


async def _send_message(
    text, history, attached_files, current_alias, current_provider, session_manager,
):
    entry = resolve_model(current_alias)
    info  = PROVIDERS[current_provider]

    console.print(f"\n[bold green]You:[/bold green] {text}")
    history.append(Message(role="user", content=text))
    session_manager.save_turn("user", text)

    console.print(f"\n[bold #6c71c4]{entry.display_name}:[/bold #6c71c4] ", end="")

    try:
        provider      = get_provider(current_alias)
        full_response = ""

        async for token in provider.stream_chat(
            messages=history,
            model=entry.model_string,
            files=attached_files or None,
        ):
            console.print(token, end="", highlight=False)
            full_response += token

        console.print("\n")
        history.append(Message(role="assistant", content=full_response))
        session_manager.save_turn("assistant", full_response)
        attached_files.clear()

    except Exception as e:
        msg = friendly_error(e, current_provider)
        console.print(f"\n{msg}\n")
