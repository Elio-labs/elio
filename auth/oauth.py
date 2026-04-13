"""
Google OAuth 2.0 — "Sign in with Google" for Gemini access.

Users visit a Google authorization URL in their browser, approve access,
paste back a code — done. No API key needed.

SETUP (one-time for Elio-Labs):
  1. Go to console.cloud.google.com
  2. Create project → APIs & Services → Credentials
  3. Create OAuth 2.0 Client ID → Desktop app
  4. Enable "Generative Language API" in the project
  5. Replace GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET below
"""

import json
import webbrowser
from pathlib import Path
from typing import Optional

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import keyring

# ── Elio's registered Google OAuth app credentials ───────────────────────────
# Replace these with your real credentials from Google Cloud Console
GOOGLE_CLIENT_ID     = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"

GOOGLE_CLIENT_CONFIG = {
    "installed": {
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
    }
}

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/generative-language",
]

SERVICE = "elio-cli"
OAUTH_KEY = "google_oauth"


def google_login() -> bool:
    """
    Run the Google OAuth 2.0 installed-app flow.
    Opens browser → user approves → paste code → token saved.
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

    try:
        flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=GOOGLE_SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )

        console.print("\n  [bold]Sign in with Google[/bold]")
        console.print("  [dim]Opening your browser...[/dim]\n")
        webbrowser.open(auth_url)
        console.print(f"  [dim]If browser didn't open, visit:[/dim]")
        console.print(f"  [cyan]{auth_url}[/cyan]\n")

        code = input("  Paste the authorization code here: ").strip()
        if not code:
            console.print("  [dim]Cancelled.[/dim]")
            return False

        flow.fetch_token(code=code)
        creds = flow.credentials

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
        from rich.console import Console
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
            # Save refreshed token back
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
