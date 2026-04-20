"""
Google Gemini provider.
Supports both API key and Google OAuth ("Sign in with Google") auth.
"""

import asyncio
from typing import AsyncIterator
from google import genai
from google.genai import types

from providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from auth.manager import get_api_key


class GeminiProvider(BaseProvider):

    def __init__(self):
        from auth.oauth import get_google_credentials
        creds = get_google_credentials()
        if creds:
            self.client = genai.Client(credentials=creds)
            return

        key = get_api_key("google")
        if key:
            self.client = genai.Client(api_key=key)
            return

        raise RuntimeError(
            "No Google credentials.\n"
            "  Option 1: Run `elio login` → choose Google → Sign in with Google\n"
            "  Option 2: Run `elio login` → choose Google → Enter API key (free at aistudio.google.com)"
        )

    def validate_credentials(self) -> bool:
        from auth.oauth import is_google_oauth_logged_in
        return get_api_key("google") is not None or is_google_oauth_logged_in()

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("gemini-fast",     "gemini-3-flash-preview",   "google", "Answers quickly"),
            ModelInfo("gemini-thinking", "gemini-3.1-pro-preview",   "google", "Solves complex problems"),
            ModelInfo("gemini-pro",      "gemini-3.1-pro-preview",   "google", "Advanced math and code with 3.1 Pro"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gemini-2.5-flash",
        files: list[FileAttachment] | None = None,
        alias: str | None = None,
    ) -> AsyncIterator[str]:
        contents = []

        # 1. Build historical context
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)]
                )
            )

        # 2. Build the final user message
        parts = []
        if files:
            for f in files:
                if f.mime_type.startswith("image/"):
                    parts.append(types.Part.from_bytes(data=f.data, mime_type=f.mime_type))
                else:
                    text_content = f.data.decode("utf-8", errors="replace")
                    parts.append(types.Part.from_text(text=f"File: {f.name}\n```\n{text_content}\n```"))

        parts.append(types.Part.from_text(text=messages[-1].content))
        contents.append(types.Content(role="user", parts=parts))

        # 3. Configure thinking based on model alias.
        #    gemini-3.1-pro-preview has native thinking — no extra config needed.
        #    gemini-3-flash-preview (fast) gets thinking_budget=0 for max speed.
        generate_config = None
        if alias == "gemini-fast":
            generate_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )

        # 4. Stream the response
        for attempt in range(3):
            try:
                stream_kwargs = dict(model=model, contents=contents)
                if generate_config:
                    stream_kwargs["config"] = generate_config

                async for chunk in await self.client.aio.models.generate_content_stream(
                    **stream_kwargs
                ):
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                err = str(e).lower()
                if ("429" in err or "rate" in err) and attempt < 2:
                    wait = 15 * (attempt + 1)
                    yield f"\n⚠️  Rate limit — retrying in {wait}s...\n"
                    await asyncio.sleep(wait)
                else:
                    yield f"\n[red]API Error:[/red] {str(e)}\n"
                    return