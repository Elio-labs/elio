import asyncio
from typing import AsyncIterator
from google import genai
from google.genai import types

from providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from auth.manager import get_api_key


class GeminiProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("google")
        if not key:
            raise RuntimeError("No Google API key. Run `elio login google`.")
        self.client = genai.Client(api_key=key)

    def validate_credentials(self) -> bool:
        return get_api_key("google") is not None

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("gemini-2.0-flash",     "gemini-2.0-flash",         "google", "Fast & free — default"),
            ModelInfo("gemini-2.0-flash-lite", "gemini-2.0-flash-lite",   "google", "Ultra-fast, lightweight"),
            ModelInfo("gemini-2.5-flash",      "gemini-2.5-flash-preview-05-20", "google", "Latest flash with thinking"),
            ModelInfo("gemini-2.5-pro",        "gemini-2.5-pro-preview-05-06",   "google", "Best reasoning & research"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gemini-2.0-flash",
        files: list[FileAttachment] | None = None,
    ) -> AsyncIterator[str]:

        # Build conversation history for the new SDK
        history = []
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            history.append(
                types.Content(role=role, parts=[types.Part(text=msg.content)])
            )

        # Build the current user message parts
        parts = []
        if files:
            for f in files:
                if f.mime_type.startswith("image/"):
                    parts.append(
                        types.Part(
                            inline_data=types.Blob(mime_type=f.mime_type, data=f.data)
                        )
                    )
                else:
                    text_content = f.data.decode("utf-8", errors="replace")
                    parts.append(types.Part(text=f"File: {f.name}\n```\n{text_content}\n```"))

        parts.append(types.Part(text=messages[-1].content))

        # Retry logic for free-tier rate limits
        for attempt in range(3):
            try:
                async for chunk in await asyncio.to_thread(
                    self._stream_sync, model, history, parts
                ):
                    yield chunk
                return
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "rate" in err or "quota" in err:
                    wait = 15 * (attempt + 1)
                    yield f"\n⚠️  Rate limit hit — retrying in {wait}s...\n"
                    await asyncio.sleep(wait)
                else:
                    raise

    def _stream_sync(self, model: str, history: list, parts: list):
        """Sync generator wrapped for asyncio.to_thread."""
        chat = self.client.chats.create(model=model, history=history)
        response = chat.send_message_stream(parts)
        for chunk in response:
            if chunk.text:
                yield chunk.text