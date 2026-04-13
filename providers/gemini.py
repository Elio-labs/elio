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
        # 1. Try Google OAuth first (user signed in with Google account)
        from auth.oauth import get_google_credentials
        creds = get_google_credentials()
        if creds:
            self.client = genai.Client(credentials=creds)
            return

        # 2. Fall back to API key
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
            ModelInfo("gemini-2.0-flash",     "gemini-2.0-flash",               "google", "Fast & free"),
            ModelInfo("gemini-2.0-flash-lite", "gemini-2.0-flash-lite",         "google", "Ultra-fast"),
            ModelInfo("gemini-2.5-flash",      "gemini-2.5-flash-preview-04-17","google", "Latest flash"),
            ModelInfo("gemini-2.5-pro",        "gemini-2.5-pro-preview-05-06",  "google", "Most capable"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gemini-2.0-flash",
        files: list[FileAttachment] | None = None,
    ) -> AsyncIterator[str]:
        contents = []

        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg.content)])
            )

        parts = []
        if files:
            for f in files:
                if f.mime_type.startswith("image/"):
                    parts.append(
                        types.Part(inline_data=types.Blob(mime_type=f.mime_type, data=f.data))
                    )
                else:
                    text_content = f.data.decode("utf-8", errors="replace")
                    parts.append(types.Part(text=f"File: {f.name}\n```\n{text_content}\n```"))

        parts.append(types.Part(text=messages[-1].content))
        contents.append(types.Content(role="user", parts=parts))

        for attempt in range(3):
            try:
                async for chunk in await self.client.aio.models.generate_content_stream(
                    model=model,
                    contents=contents,
                ):
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "rate" in err or "quota" in err:
                    wait = 15 * (attempt + 1)
                    yield f"\n⚠️  Rate limit — retrying in {wait}s...\n"
                    await asyncio.sleep(wait)
                else:
                    raise
