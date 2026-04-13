import httpx


def friendly_error(exc: Exception, provider: str = "") -> str:
    msg = str(exc).lower()

    if "invalid_api_key" in msg or "authentication" in msg or "unauthorized" in msg or "401" in msg:
        return (
            "[red]Invalid API key.[/red]\n"
            "  Run [bold cyan]elio login[/bold cyan] and re-enter your key."
        )

    if "billing" in msg or "quota" in msg or "insufficient_quota" in msg or "429" in msg or "402" in msg:
        tip = ""
        if provider in ("anthropic", "openai"):
            tip = (
                "\n\n  [dim]💡 Switch to a FREE model:[/dim]"
                "\n     [cyan]/provider[/cyan] → choose [bold]Groq[/bold] (Llama 3.3, Mixtral — completely free)"
                "\n     [cyan]/provider[/cyan] → choose [bold]Google[/bold] (Gemini 2.0 Flash — free tier)"
            )
        return f"[yellow]Billing issue — no credits on this account.[/yellow]{tip}"

    if "rate_limit" in msg or "rate limit" in msg:
        return "[yellow]Rate limit hit. Wait a moment and try again.[/yellow]"

    if "context_length" in msg or "too long" in msg or "maximum context" in msg:
        return (
            "[yellow]Message too long for this model.[/yellow]\n"
            "  Run [bold cyan]/clear[/bold cyan] to reset the conversation context."
        )

    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return "[red]No internet connection. Check your network and retry.[/red]"

    if "overloaded" in msg or "529" in msg or "503" in msg:
        return "[yellow]Provider is overloaded right now. Retry in a few seconds.[/yellow]"

    if "model_not_found" in msg or "does not exist" in msg or "invalid model" in msg:
        return (
            "[red]Model not found.[/red]\n"
            "  Run [bold cyan]/models[/bold cyan] to see available models."
        )

    return f"[red]Error: {exc}[/red]"
