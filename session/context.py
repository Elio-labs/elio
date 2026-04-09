from elio.providers.base import Message

# Rough estimate: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4


def truncate_history(
    messages: list[Message],
    max_tokens: int = 8000,
) -> list[Message]:
    """
    Return only as many recent messages as fit within max_tokens.
    Always keeps the most recent messages (drops oldest first).
    The first message (system-like context) is always kept if it exists.
    """
    budget = max_tokens * CHARS_PER_TOKEN
    result = []
    total_chars = 0

    # Walk from newest to oldest
    for msg in reversed(messages):
        cost = len(msg.content)
        if total_chars + cost > budget:
            break
        result.append(msg)
        total_chars += cost

    return list(reversed(result))