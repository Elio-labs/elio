from pathlib import Path
from datetime import datetime

from session.history import (
    init_db, create_session, append_message, load_session, list_sessions
)
from providers.base import Message


class SessionManager:
    """
    Wraps the SQLite history layer.
    The TUI creates one instance and calls these methods on each turn.
    """

    def __init__(self):
        init_db()
        self.session_id: str | None = None
        self.model: str = "claude"

    def start_new(self, model: str):
        """Begin a fresh session — call this when user opens TUI or presses Ctrl+N."""
        self.model = model
        title = f"Session {datetime.now().strftime('%b %d %H:%M')}"
        self.session_id = create_session(model=model, title=title)

    def load(self, session_id: str) -> list[Message]:
        """Load a previous session. Returns the message list for the TUI history."""
        self.session_id = session_id
        rows = load_session(session_id)
        return [Message(role=r["role"], content=r["content"]) for r in rows]

    def save_turn(self, role: str, content: str):
        """Append one message. Called after every user message and every AI response."""
        if self.session_id is None:
            self.start_new(self.model)
        append_message(self.session_id, role, content)

    def recent_sessions(self) -> list[dict]:
        return list_sessions()

    def export_markdown(self, messages: list[Message], export_dir: str = "~") -> str:
        """Write the current conversation as a .md file. Returns the path."""
        out_dir = Path(export_dir).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"elio_session_{ts}.md"

        lines = [f"# Elio Session — {ts}\n"]
        for msg in messages:
            prefix = "**You:**" if msg.role == "user" else "**Assistant:**"
            lines.append(f"{prefix}\n\n{msg.content}\n\n---\n")

        path.write_text("\n".join(lines))
        return str(path)