import keyring
from typing import Optional

# Keyring service name — all keys are stored under this namespace
SERVICE = "elio-cli"

# Valid provider names Elio supports
PROVIDERS = ["anthropic", "openai", "google"]


def set_api_key(provider: str, key: str):
    """
    Save an API key to the OS keyring.
    macOS → Keychain, Windows → Credential Manager, Linux → Secret Service
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Must be one of {PROVIDERS}")
    keyring.set_password(SERVICE, provider, key.strip())


def get_api_key(provider: str) -> Optional[str]:
    """Retrieve an API key. Returns None if not set."""
    return keyring.get_password(SERVICE, provider)


def delete_api_key(provider: str):
    """Remove a key from the keyring (used by elio logout)."""
    try:
        keyring.delete_password(SERVICE, provider)
    except keyring.errors.PasswordDeleteError:
        pass  # Already gone — that's fine


def get_connected_providers() -> list[str]:
    """Return list of providers that have a key stored."""
    return [p for p in PROVIDERS if get_api_key(p) is not None]


def logout_all():
    """Wipe every stored credential — used by `elio logout`."""
    for provider in PROVIDERS:
        delete_api_key(provider)