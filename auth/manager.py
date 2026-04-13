import keyring
from typing import Optional

SERVICE  = "elio-cli"

# All providers Elio supports
PROVIDERS = ["groq", "google", "anthropic", "openai"]


def set_api_key(provider: str, key: str):
    """Save an API key to the OS keyring."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Must be one of {PROVIDERS}")
    keyring.set_password(SERVICE, f"apikey_{provider}", key.strip())


def get_api_key(provider: str) -> Optional[str]:
    """Retrieve an API key. Returns None if not set."""
    return keyring.get_password(SERVICE, f"apikey_{provider}")


def delete_api_key(provider: str):
    """Remove a key from the keyring."""
    try:
        keyring.delete_password(SERVICE, f"apikey_{provider}")
    except keyring.errors.PasswordDeleteError:
        pass


def get_connected_providers() -> list[str]:
    """Return list of providers that have a key OR OAuth token stored."""
    from auth.oauth import is_google_oauth_logged_in
    connected = []
    for p in PROVIDERS:
        if get_api_key(p):
            connected.append(p)
        elif p == "google" and is_google_oauth_logged_in():
            connected.append(p)
    return connected


def is_provider_ready(provider: str) -> bool:
    """True if this provider has an API key or (for google) a valid OAuth token."""
    if get_api_key(provider):
        return True
    if provider == "google":
        from auth.oauth import is_google_oauth_logged_in
        return is_google_oauth_logged_in()
    return False


def logout_all():
    """Wipe every stored credential."""
    for provider in PROVIDERS:
        delete_api_key(provider)
    from auth.oauth import google_logout
    google_logout()
