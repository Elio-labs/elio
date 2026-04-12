from pydantic import BaseModel, Field
from typing import Literal, Optional


class ElioConfig(BaseModel):
    # No hardcoded default — forces the "Select your AI" selector on launch
    default_provider: Optional[str] = None

    # No hardcoded default model
    default_model: Optional[str] = None

    # Visual theme for the TUI
    theme: Literal["dark", "light", "high-contrast"] = "dark"

    # How many tokens of history to keep in the context window
    max_context_tokens: int = Field(default=8000, ge=1000, le=200000)

    # Auto-save conversations after every message
    auto_save: bool = True

    # Show token counter in the input bar
    show_token_count: bool = True

    # Streaming speed — tokens per second target (None = max speed)
    stream_delay_ms: int = 0

    # Directory where exported markdown sessions are saved
    export_dir: str = "~/elio-exports"

    # Log level for ~/.elio/logs/
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"