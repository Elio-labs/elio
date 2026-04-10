import base64
from typing import AsyncIterator
from openai import AsyncOpenAI

from providers.base import BaseProvider, Message, FileAttachment, ModelInfo
from auth.manager import get_api_key


class OpenAIProvider(BaseProvider):

    def __init__(self):
        key = get_api_key("openai")
        if not key:
            raise RuntimeError("No OpenAI API key. Run `elio login openai`.")
        self.client = AsyncOpenAI(api_key=key)

    def validate_credentials(self) -> bool:
        return get_api_key("openai") is not None

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo("gpt-4o-mini",  "gpt-4o-mini",  "openai", "Fast & very cheap — free credits"),
            ModelInfo("gpt-4o",       "gpt-4o",       "openai", "Multi-modal, writing & creativity"),
            ModelInfo("gpt-4.1",      "gpt-4.1",      "openai", "Latest & most capable"),
            ModelInfo("gpt-4.1-mini", "gpt-4.1-mini", "openai", "Fast latest-gen"),
            ModelInfo("gpt-4.1-nano", "gpt-4.1-nano", "openai", "Ultra-fast, cheapest"),
        ]

    async def stream_chat(
        self,
        messages: list[Message],
        model: str = "gpt-4o-mini",
        files: list[FileAttachment] | None = None,
    ) -> AsyncIterator[str]:
        api_messages = []

        for i, msg in enumerate(messages):
            if i < len(messages) - 1 or msg.role == "assistant":
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                content = []

                if files:
                    for f in files:
                        if f.mime_type.startswith("image/"):
                            b64 = base64.b64encode(f.data).decode()
                            content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{f.mime_type};base64,{b64}"},
                            })
                        else:
                            text_content = f.data.decode("utf-8", errors="replace")
                            content.append({
                                "type": "text",
                                "text": f"File: {f.name}\n```\n{text_content}\n```",
                            })

                content.append({"type": "text", "text": msg.content})
                api_messages.append({"role": "user", "content": content})

        stream = await self.client.chat.completions.create(
            model=model,
            messages=api_messages,
            max_tokens=4096,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta