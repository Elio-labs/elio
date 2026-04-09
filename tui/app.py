from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical
from textual.binding import Binding
from textual import work

from providers.registry import get_provider, resolve_model
from providers.base import Message
from config.loader import load_config
from cli.selector import ModelSelectorScreen
from session.manager import SessionManager

from textual.screen import ModalScreen
from textual.widgets import Input


class FilePathPromptScreen(ModalScreen[str]):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Enter file path to attach and press Enter...")

    def on_input_submitted(self, event: Input.Submitted):
        self.dismiss(event.value)


class ElioApp(App):
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
        Binding("ctrl+u", "attach_file", "Attach File"),
        Binding("ctrl+c", "quit",          "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.current_alias = self.config.default_model
        self.history: list[Message] = []
        self.attached_files = []
        self.current_session_id = None
        self.session_manager = SessionManager()
        self.session_manager.start_new(self.current_alias)
        self._model_selected = False  # Track if user has picked a model

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", markup=True, highlight=True)
        yield Input(
            placeholder="Select a model first... (loading)",
            id="user-input",
        )
        yield Footer()

    def on_mount(self):
        self.title = "Elio"
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold cyan]Elio[/bold cyan] — Welcome! Select a model to get started.\n")
        # Auto-open the model selector on first launch
        self._launch_model_selector()

    @work(exclusive=True)
    async def _launch_model_selector(self):
        """Show model selector on startup. Runs in a worker so push_screen_wait works."""
        alias = await self.push_screen_wait(ModelSelectorScreen())
        if alias:
            self._apply_model(alias)
        else:
            # User pressed Esc without choosing — fall back to default
            self._apply_model(self.config.default_model)

    def _apply_model(self, alias: str):
        """Apply the selected model alias — update title, placeholder, session."""
        self.current_alias = alias
        self._model_selected = True
        entry = resolve_model(alias)
        self.title = f"Elio — {alias}"
        self.session_manager.start_new(alias)
        inp = self.query_one("#user-input", Input)
        inp.placeholder = f"[{entry.model_string}] Message... (Ctrl+M to switch model)"
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]Model:[/bold cyan] {entry.description} ([yellow]{entry.model_string}[/yellow])\n")
        log.write("[bold cyan]Elio[/bold cyan] — type a message and press Enter.\n")

    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        if text.startswith("/"):
            await self._handle_slash(text)
            return

        # _send_message is @work-decorated → returns a Worker, don't await it
        self._send_message(text)

    @work(exclusive=False)
    async def _send_message(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold green]You:[/bold green] {text}\n")

        self.history.append(Message(role="user", content=text))
        self.session_manager.save_turn("user", text)

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
            self.session_manager.save_turn("assistant", full_response)
            self.attached_files = []

        except Exception as e:
            log.write(f"[bold red]Error:[/bold red] {e}\n")

    async def _handle_slash(self, cmd: str):
        from tui.commands_router import route_command
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
        self.session_manager.start_new(self.current_alias)

    def action_model_select(self):
        """Open the model selector. Uses @work to run push_screen_wait in a worker."""
        self._do_model_select()

    @work(exclusive=True)
    async def _do_model_select(self):
        alias = await self.push_screen_wait(ModelSelectorScreen())
        if alias:
            self.current_alias = alias
            self.title = f"Elio — {alias}"
            entry = resolve_model(alias)
            inp = self.query_one("#user-input", Input)
            inp.placeholder = f"[{entry.model_string}] Message... (Ctrl+M to switch model)"
            log = self.query_one("#chat-log", RichLog)
            log.write(f"[yellow]→ Switched to {alias} ({entry.model_string})[/yellow]\n")
            self.session_manager.start_new(alias)

    def action_attach_file(self):
        """Open file path prompt. Uses @work to run push_screen_wait in a worker."""
        self._do_attach_file()

    @work(exclusive=True)
    async def _do_attach_file(self):
        from tui.commands_router import route_command

        log = self.query_one("#chat-log", RichLog)
        path = await self.push_screen_wait(FilePathPromptScreen())
        if path:
            result = await route_command(f"/attach {path}", self)
            log.write(result.output + "\n")


def run_tui(alias: str | None = None):
    app = ElioApp()
    if alias:
        app.current_alias = alias
    app.run()