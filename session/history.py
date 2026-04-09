import sqlite3
from pathlib import Path
from datetime import datetime
import uuid

DB_PATH = Path.home() / ".elio" / "history.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True, parents=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id        TEXT PRIMARY KEY,
                title     TEXT,
                model     TEXT,
                created   TEXT,
                updated   TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         TEXT PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id),
                role       TEXT,
                content    TEXT,
                timestamp  TEXT
            );
        """)


def create_session(model: str, title: str = "New Session") -> str:
    """Create a new session row and return its ID."""
    session_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?)",
            (session_id, title, model, now, now),
        )
    return session_id


def append_message(session_id: str, role: str, content: str):
    """Add a message to an existing session."""
    now = datetime.utcnow().isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, role, content, now),
        )
        # Update the session's updated timestamp
        con.execute(
            "UPDATE sessions SET updated=? WHERE id=?",
            (now, session_id),
        )


def load_session(session_id: str) -> list[dict]:
    """Return all messages for a session, oldest first."""
    with _conn() as con:
        rows = con.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
    return [{"role": r, "content": c} for r, c in rows]


def list_sessions(limit: int = 20) -> list[dict]:
    """Return recent sessions, newest first."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, title, model, updated FROM sessions ORDER BY updated DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"id": i, "title": t, "model": m, "updated": u} for i, t, m, u in rows]