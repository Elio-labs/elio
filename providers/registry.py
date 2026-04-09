from dataclasses import dataclass
from elio.providers.base import BaseProvider


@dataclass
class ModelEntry:
    alias: str
    model_string: str      # exact string sent to provider API
    provider_name: str     # "anthropic" | "openai" | "google"
    description: str


# ── The single source of truth for all model aliases ────────────────────────
MODEL_REGISTRY: dict[str, ModelEntry] = {
    # Claude models
    "claude":   ModelEntry("claude",   "claude-sonnet-4-5",  "anthropic", "Best for coding & reasoning"),
    "coding":   ModelEntry("coding",   "claude-sonnet-4-5",  "anthropic", "Alias for claude"),
    "fast":     ModelEntry("fast",     "claude-haiku-4-5",   "anthropic", "Fastest & cheapest"),

    # OpenAI models (added Day 3)
    "gpt":      ModelEntry("gpt",      "gpt-4o",             "openai",    "Best for writing & creativity"),
    "writing":  ModelEntry("writing",  "gpt-4o",             "openai",    "Alias for gpt"),
    "vision":   ModelEntry("vision",   "gpt-4o",             "openai",    "Best multi-modal model"),

    # Gemini models (added Day 3)
    "gemini":   ModelEntry("gemini",   "gemini-2.5-pro",     "google",    "Best for research & summaries"),
    "research": ModelEntry("research", "gemini-2.5-pro",     "google",    "Alias for gemini"),
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
        from elio.providers.claude import ClaudeProvider
        return ClaudeProvider()

    if entry.provider_name == "openai":
        from elio.providers.openai import OpenAIProvider
        return OpenAIProvider()

    if entry.provider_name == "google":
        from elio.providers.gemini import GeminiProvider
        return GeminiProvider()

    raise ValueError(f"No provider class for '{entry.provider_name}'")