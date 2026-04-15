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
            ModelInfo("gemini-fast",    "gemini-2.5-flash",  "google", "Fast & free"),
            ModelInfo("gemini-thinking","gemini-2.0-flash-thinking-exp-01-21", "google", "Deep reasoning"),
            ModelInfo("gemini-pro",     "gemini-3.1-pro",    "google", "Most capable"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gemini-2.5-flash",
        files: list[FileAttachment] | None = None,
    ) -> AsyncIterator[str]:
        contents = []

        # 1. Build Historical Context
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            contents.append(
                # Pass text directly as a string part instead of using types.Part(text=...)
                types.Content(role=role, parts=[msg.content])
            )

        # 2. Build the final User Message
        parts = []
        if files:
            for f in files:
                if f.mime_type.startswith("image/"):
                    # Safely load image bytes using the new SDK method
                    parts.append(
                        types.Part.from_bytes(data=f.data, mime_type=f.mime_type)
                    )
                else:
                    text_content = f.data.decode("utf-8", errors="replace")
                    parts.append(f"File: {f.name}\n```\n{text_content}\n```")

        # Append the user's text prompt
        parts.append(messages[-1].content)
        contents.append(types.Content(role="user", parts=parts))

        # 3. Stream the response
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
                # Properly catch and retry 429 Rate Limits
                if ("429" in err or "rate" in err) and attempt < 2:
                    wait = 15 * (attempt + 1)
                    yield f"\n⚠️ Rate limit — retrying in {wait}s...\n"
                    import asyncio
                    await asyncio.sleep(wait)
                else:
                    yield f"\n[red]API Error:[/red] {str(e)}\n"
                    return