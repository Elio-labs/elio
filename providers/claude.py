import base64
from typing import AsyncIterator
import anthropic

from elio.providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from elio.auth.manager import get_api_key


class ClaudeProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("anthropic")
        if not key:
            raise RuntimeError(
                "No Anthropic API key found. Run `elio login` first."
            )
        # Async client — all calls are awaited inside stream_chat
        self.client = anthropic.AsyncAnthropic(api_key=key)

    def validate_credentials(self) -> bool:
        return get_api_key("anthropic") is not None

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("claude",   "claude-sonnet-4-5", "anthropic", "Best for coding & reasoning"),
            ModelInfo("fast",     "claude-haiku-4-5",  "anthropic", "Fastest & cheapest Claude"),
            ModelInfo("coding",   "claude-sonnet-4-5", "anthropic", "Alias for claude"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "claude-sonnet-4-5",
        files: list[FileAttachment] | None = None,
    ) -> AsyncIterator[str]:
        # Build the content list for the last user message
        # (previous messages in the list are just role/text pairs)
        api_messages = []

        for i, msg in enumerate(messages):
            if i < len(messages) - 1 or msg.role == "assistant":
                # Historical messages — plain text only
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                # Last user message — may have file attachments
                content = []

                # Add file blocks before the text
                if files:
                    for f in files:
                        if f.mime_type.startswith("image/"):
                            content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": f.mime_type,
                                    "data": base64.b64encode(f.data).decode(),
                                },
                            })
                        elif f.mime_type == "application/pdf":
                            content.append({
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": base64.b64encode(f.data).decode(),
                                },
                            })
                        else:
                            # Text file — inject as a code block
                            text_content = f.data.decode("utf-8", errors="replace")
                            content.append({
                                "type": "text",
                                "text": f"```{f.name}\n{text_content}\n```",
                            })

                content.append({"type": "text", "text": msg.content})
                api_messages.append({"role": "user", "content": content})

        # Open a streaming context and yield each token as it arrives
        async with self.client.messages.stream(
            model=model,
            max_tokens=4096,
            messages=api_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text