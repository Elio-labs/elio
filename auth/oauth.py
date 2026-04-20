"""
Google OAuth 2.0 — "Sign in with Google" for Gemini access.

Uses the loopback (localhost) flow — the only supported flow for installed
desktop apps after Google deprecated the OOB (out-of-band) flow in 2023.

Flow:
  1. Elio opens the Google authorization URL in the user's browser.
  2. A local HTTP server on 127.0.0.1 catches the redirect with the auth code.
  3. Tokens are stored in the OS keyring — no API key needed.

SETUP (one-time for Elio-Labs):
  1. Go to console.cloud.google.com
  2. Create project → APIs & Services → Credentials
  3. Create OAuth 2.0 Client ID → Desktop app  ← must be "Desktop app" type
  4. Enable "Generative Language API" in the project
  5. Replace GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET below
"""

import json
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import keyring

# ── Elio's registered Google OAuth app credentials ───────────────────────────
# Replace these with your real credentials from Google Cloud Console.
# The client type MUST be "Desktop app" (not "Web application").
GOOGLE_CLIENT_ID     = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/generative-language",
]

SERVICE   = "elio-cli"
OAUTH_KEY = "google_oauth"


def _find_free_port() -> int:
    """Bind to port 0 to let the OS pick a free port, then release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_loopback_flow(console) -> Optional[Credentials]:
    """
    Implements the loopback / localhost redirect flow.
    Opens a browser → user approves → local server captures the code → returns Credentials.
    """
    port = _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}"

    client_config = {
        "installed": {
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [redirect_uri, "http://localhost"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    # Container for the captured auth code (shared between threads)
    result = {"code": None, "error": None}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                result["code"] = params["code"][0]
                body = b"<html><body><h2>Elio: Sign-in successful!</h2><p>You can close this tab.</p></body></html>"
            elif "error" in params:
                result["error"] = params["error"][0]
                body = b"<html><body><h2>Elio: Sign-in cancelled.</h2><p>You can close this tab.</p></body></html>"
            else:
                body = b"<html><body><p>Waiting...</p></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # Suppress server logs

    server = HTTPServer(("127.0.0.1", port), _Handler)
    server.timeout = 120  # 2-minute timeout

    console.print("  [dim]Opening your browser for Google sign-in...[/dim]")
    webbrowser.open(auth_url)
    console.print(f"  [dim]If the browser didn't open, visit:[/dim]")
    console.print(f"  [cyan]{auth_url}[/cyan]\n")
    console.print("  [dim]Waiting for Google to redirect back (up to 2 min)...[/dim]")

    # Handle exactly one request (the redirect)
    server.handle_request()
    server.server_close()

    if result["error"]:
        console.print(f"  [red]Google sign-in was denied: {result['error']}[/red]")
        return None

    if not result["code"]:
        console.print("  [red]No authorization code received. Did you approve in the browser?[/red]")
        return None

    flow.fetch_token(code=result["code"])
    return flow.credentials


def google_login() -> bool:
    """
    Run the Google OAuth 2.0 loopback flow.
    Opens browser → user approves → token auto-captured → saved to keyring.
    Returns True on success.
    """
    from rich.console import Console
    console = Console()

    if GOOGLE_CLIENT_ID == "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com":
        console.print(
            "\n  [yellow]! Google OAuth is not configured yet.[/yellow]\n"
            "  [dim]Elio-Labs: add your Google Cloud OAuth credentials to auth/oauth.py[/dim]\n"
            "  [dim]Or use a Gemini API key instead: [cyan]elio login google[/cyan][/dim]\n"
        )
        return False

    console.print("\n  [bold]Sign in with Google[/bold]")

    try:
        creds = _run_loopback_flow(console)
        if creds is None:
            return False

        # Save to keyring as JSON
        token_data = {
            "token":         creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri":     creds.token_uri,
            "client_id":     creds.client_id,
            "client_secret": creds.client_secret,
            "scopes":        list(creds.scopes or GOOGLE_SCOPES),
        }
        keyring.set_password(SERVICE, OAUTH_KEY, json.dumps(token_data))
        console.print("  [green]✓ Signed in with Google successfully.[/green]\n")
        return True

    except Exception as e:
        Console().print(f"  [red]Google sign-in failed: {e}[/red]")
        return False


def get_google_credentials() -> Optional[Credentials]:
    """
    Load stored Google OAuth credentials.
    Auto-refreshes if the access token is expired.
    Returns None if not logged in or token is invalid.
    """
    raw = keyring.get_password(SERVICE, OAUTH_KEY)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", GOOGLE_SCOPES),
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            data["token"] = creds.token
            keyring.set_password(SERVICE, OAUTH_KEY, json.dumps(data))

        return creds if creds.valid else None
    except Exception:
        return None


def google_logout():
    """Remove stored Google OAuth token."""
    try:
        keyring.delete_password(SERVICE, OAUTH_KEY)
    except Exception:
        pass


def is_google_oauth_logged_in() -> bool:
    """Return True if a valid Google OAuth session exists."""
    return get_google_credentials() is not None
