import base64
from typing import AsyncIterator
import google.generativeai as genai

from providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from auth.manager import get_api_key


class GeminiProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("google")
        if not key:
            raise RuntimeError("No Google API key. Run `elio login`.")
        genai.configure(api_key=key)

    def validate_credentials(self) -> bool:
        return get_api_key("google") is not None

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("gemini",   "gemini-2.5-pro", "google", "Research & web-grounded summaries"),
            ModelInfo("research", "gemini-2.5-pro", "google", "Alias for gemini"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gemini-2.5-pro",
        files: list[FileAttachment] | None = None,
    ) -> AsyncIterator[str]:
        # Convert history to Gemini's format
        history = []
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            history.append({"role": role, "parts": [msg.content]})

        gemini_model = genai.GenerativeModel(model_name=model)
        chat = gemini_model.start_chat(history=history)

        # Build the current user message parts
        parts = []
        if files:
            for f in files:
                if f.mime_type.startswith("image/"):
                    parts.append({"mime_type": f.mime_type, "data": f.data})
                else:
                    text_content = f.data.decode("utf-8", errors="replace")
                    parts.append(f"File: {f.name}\n```\n{text_content}\n```")

        parts.append(messages[-1].content)

        response = await chat.send_message_async(parts, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text