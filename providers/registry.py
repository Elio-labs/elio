"""
Elio Model Registry — single source of truth for all providers and models.

Organized as Provider → Models hierarchy.
Users pick a provider first, then a model under that provider.
"""

from dataclasses import dataclass, field
from providers.base import BaseProvider


@dataclass
class ModelEntry:
    alias: str            # internal key  e.g. "gemini-2.0-flash"
    display_name: str     # shown to user e.g. "Gemini 2.0 Flash"
    model_string: str     # sent to API   e.g. "gemini-2.0-flash"
    provider_name: str    # "anthropic" | "openai" | "google"
    description: str      # short blurb
    is_free: bool = False # whether this model is free to use


@dataclass
class ProviderInfo:
    key: str              # "google" | "anthropic" | "openai"
    name: str             # "Google"
    brand: str            # "Gemini"
    has_free: bool        # whether this provider has any free-tier models


# ── Provider metadata ───────────────────────────────────────────────────────

PROVIDERS: dict[str, ProviderInfo] = {
    "google": ProviderInfo(
        key="google", name="Google", brand="Gemini", has_free=True,
    ),
    "anthropic": ProviderInfo(
        key="anthropic", name="Anthropic", brand="Claude", has_free=True,
    ),
    "openai": ProviderInfo(
        key="openai", name="OpenAI", brand="GPT", has_free=True,
    ),
}

# ── Provider display order ──────────────────────────────────────────────────

PROVIDER_ORDER = ["google", "anthropic", "openai"]

# ── The single source of truth for all model aliases ────────────────────────

MODEL_REGISTRY: dict[str, ModelEntry] = {
    # ─── Google (Gemini) ─────────────────────────────────────────────────
    "gemini-2.0-flash": ModelEntry(
        alias="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        model_string="gemini-2.0-flash",
        provider_name="google",
        description="Fast & free — default",
        is_free=True,
    ),
    "gemini-2.0-flash-lite": ModelEntry(
        alias="gemini-2.0-flash-lite",
        display_name="Gemini 2.0 Flash Lite",
        model_string="gemini-2.0-flash-lite",
        provider_name="google",
        description="Ultra-fast, lightweight",
        is_free=True,
    ),
    "gemini-2.5-flash": ModelEntry(
        alias="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        model_string="gemini-2.5-flash-preview-04-17",
        provider_name="google",
        description="Latest flash with thinking",
        is_free=True,
    ),
    "gemini-2.5-pro": ModelEntry(
        alias="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        model_string="gemini-2.5-pro-preview-05-06",
        provider_name="google",
        description="Best reasoning & research",
        is_free=False,
    ),

    # ─── Anthropic (Claude) ──────────────────────────────────────────────
    "claude-sonnet": ModelEntry(
        alias="claude-sonnet",
        display_name="Claude Sonnet 4.6",
        model_string="claude-sonnet-4-6",
        provider_name="anthropic",
        description="Best for coding & reasoning",
        is_free=False,
    ),
    "claude-haiku": ModelEntry(
        alias="claude-haiku",
        display_name="Claude Haiku 4.5",
        model_string="claude-haiku-4-5-20251001",
        provider_name="anthropic",
        description="Fast & affordable",
        is_free=False,
    ),

    # ─── OpenAI (GPT) ───────────────────────────────────────────────────
    "gpt-4o-mini": ModelEntry(
        alias="gpt-4o-mini",
        display_name="GPT-4o Mini",
        model_string="gpt-4o-mini",
        provider_name="openai",
        description="Fast & very cheap — free credits",
        is_free=True,
    ),
    "gpt-4o": ModelEntry(
        alias="gpt-4o",
        display_name="GPT-4o",
        model_string="gpt-4o",
        provider_name="openai",
        description="Multi-modal, writing & creativity",
        is_free=True,
    ),
    "gpt-4.1": ModelEntry(
        alias="gpt-4.1",
        display_name="GPT-4.1",
        model_string="gpt-4.1",
        provider_name="openai",
        description="Latest & most capable",
        is_free=False,
    ),
    "gpt-4.1-mini": ModelEntry(
        alias="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        model_string="gpt-4.1-mini",
        provider_name="openai",
        description="Fast latest-gen",
        is_free=False,
    ),
    "gpt-4.1-nano": ModelEntry(
        alias="gpt-4.1-nano",
        display_name="GPT-4.1 Nano",
        model_string="gpt-4.1-nano",
        provider_name="openai",
        description="Ultra-fast, cheapest",
        is_free=True,
    ),
}

# ── Models grouped by provider (display order) ─────────────────────────────

PROVIDER_MODELS: dict[str, list[str]] = {
    "google": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
    "anthropic": [
        "claude-sonnet",
        "claude-haiku",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
    ],
}


def resolve_model(alias: str) -> ModelEntry:
    """Look up an alias. Raises KeyError with helpful message if not found."""
    if alias not in MODEL_REGISTRY:
        valid = ", ".join(MODEL_REGISTRY.keys())
        raise KeyError(f"Unknown model '{alias}'. Valid aliases: {valid}")
    return MODEL_REGISTRY[alias]


def get_provider(alias: str) -> BaseProvider:
    """Resolve alias → instantiate the correct provider class."""
    entry = resolve_model(alias)

    if entry.provider_name == "anthropic":
        from providers.claude import ClaudeProvider
        return ClaudeProvider()

    if entry.provider_name == "openai":
        from providers.openai import OpenAIProvider
        return OpenAIProvider()

    if entry.provider_name == "google":
        from providers.gemini import GeminiProvider
        return GeminiProvider()

    raise ValueError(f"No provider class for '{entry.provider_name}'")


def get_models_for_provider(provider_key: str) -> list[ModelEntry]:
    """Return all ModelEntry objects for a given provider, in display order."""
    aliases = PROVIDER_MODELS.get(provider_key, [])
    return [MODEL_REGISTRY[a] for a in aliases]


def get_default_model_for_provider(provider_key: str) -> ModelEntry:
    """Return the first (default) model for a provider."""
    aliases = PROVIDER_MODELS.get(provider_key, [])
    if not aliases:
        raise ValueError(f"No models registered for provider '{provider_key}'")
    return MODEL_REGISTRY[aliases[0]]