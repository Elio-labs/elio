from typing import Callable, AsyncIterator
import httpx


def friendly_error(exc: Exception) -> str:
    """
    Convert a raw exception into a short, actionable message for the TUI log.
    """
    msg = str(exc).lower()

    if "invalid_api_key" in msg or "authentication" in msg or "unauthorized" in msg:
        return "[red]Invalid API key. Run `elio login` and re-enter your key.[/red]"

    if "rate_limit" in msg or "429" in msg:
        return "[yellow]Rate limit hit. Wait a moment and try again.[/yellow]"

    if "context_length" in msg or "too long" in msg:
        return "[yellow]Message too long. Run /clear to reset the context.[/yellow]"

    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return "[red]No internet connection. Check your network and retry.[/red]"

    if "overloaded" in msg or "529" in msg:
        return "[yellow]Provider is overloaded. Retry in a few seconds.[/yellow]"

    if "billing" in msg or "quota" in msg:
        return "[red]Billing issue. Check your API account credits.[/red]"

    # Generic fallback
    return f"[red]Error: {exc}[/red]"


async def safe_stream(stream_gen: AsyncIterator[str]):
    """
    Wrap a streaming generator. Yields tokens normally,
    but catches exceptions and yields a friendly error string.
    Usage: async for token in safe_stream(provider.stream_chat(...)):
    """
    try:
        async for token in stream_gen:
            yield token
    except Exception as e:
        yield "\n" + friendly_error(e)