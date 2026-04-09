from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from textual.binding import Binding
from textual import work

from elio.providers.registry import get_provider, resolve_model
from elio.providers.base import Message
from elio.config.loader import load_config
from elio.cli.selector import ModelSelectorScreen
# Add to __init__ in ElioApp:
from elio.session.manager import SessionManager
self.session_manager = SessionManager()
self.session_manager.start_new(self.current_alias)



class ElioApp(App):
    """The main Elio TUI application."""

    CSS = """
    Screen {
        background: $background;
    }
    #chat-log {
        height: 1fr;
        border: none;
        padding: 1 2;
    }
    #user-input {
        dock: bottom;
        height: 3;
        border: solid $accent;
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+m", "model_select", "Switch Model"),
        Binding("ctrl+n", "new_session",   "New Session"),
        Binding("ctrl+l", "clear_chat",   "Clear"),
        Binding("ctrl+c", "quit",          "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.current_alias = self.config.default_model
        self.history: list[Message] = []
        self.attached_files = []   # filled by file handler (Day 4)
        self.current_session_id = None

    def compose(self) -> ComposeResult:
        entry = resolve_model(self.current_alias)
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", markup=True, highlight=True)
        yield Input(
            placeholder=f"[{entry.model_string}] Message... (Ctrl+M to switch model)",
            id="user-input"
        )
        yield Footer()

    def on_mount(self):
        self.title = f"Elio — {self.current_alias}"
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold cyan]Elio[/bold cyan] — type a message and press Enter.\n")

    async def on_input_submitted(self, event: Input.Submitted):
        """Fires when the user presses Enter in the input bar."""
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        # Handle slash commands (Day 5 expands this)
        if text.startswith("/"):
            await self._handle_slash(text)
            return

        await self._send_message(text)

    @work(exclusive=False)
    async def _send_message(self, text: str):
        """Run the API call in a background worker so the UI stays responsive."""
        log = self.query_one("#chat-log", RichLog)

        log.write(f"[bold green]You:[/bold green] {text}\n")

        self.history.append(Message(role="user", content=text))

        try:
            provider = get_provider(self.current_alias)
            entry = resolve_model(self.current_alias)

            log.write(f"[bold blue]{entry.model_string}:[/bold blue] ")
            full_response = ""

            async for token in provider.stream_chat(
                messages=self.history,
                model=entry.model_string,
                files=self.attached_files or None,
            ):
                log.write(token, animate=False)
                full_response += token

            log.write("\n")
            self.history.append(Message(role="assistant", content=full_response))
            self.attached_files = []  # clear after send

        except Exception as e:
            log.write(f"[bold red]Error:[/bold red] {e}\n")

    async def _handle_slash(self, cmd: str):
        from elio.tui.commands_router import route_command
        log = self.query_one("#chat-log", RichLog)
        result = await route_command(cmd, self)
        log.write(result.output + "\n")

        async def action_clear_chat(self):
            self.query_one("#chat-log", RichLog).clear()
            self.history = []

        async def action_new_session(self):
            self.history = []
            self.attached_files = []
            self.query_one("#chat-log", RichLog).clear()

# Save each turn in _send_message, after appending to self.history:
self.session_manager.save_turn("user", text)
# ... and after full_response is assembled:
self.session_manager.save_turn("assistant", full_response)

# Add Ctrl+U binding to BINDINGS list:
Binding("ctrl+u", "attach_file", "Attach File"),

# Entry point called by elio/cli/main.py
def run_tui(alias: str | None = None):
    app = ElioApp()
    if alias:
        app.current_alias = alias
    app.run()


async def action_model_select(self):
    """Open the model selector modal (Ctrl+M)."""
    alias = await self.push_screen_wait(ModelSelectorScreen())
    if alias:
        self.current_alias = alias
        self.title = f"Elio — {alias}"
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[yellow]→ Switched to {alias}[/yellow]\n")

# Add action:
async def action_attach_file(self):
    """Open a simple path prompt for file attachment."""
    log = self.query_one("#chat-log", RichLog)
    path = await self.push_screen_wait(FilePathPromptScreen())
    if path:
        result = await route_command(f"/attach {path}", self)
        log.write(result.output + "\n")