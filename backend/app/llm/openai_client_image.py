"""DALL-E image client. Returns raw PNG bytes; the caller uploads to GCS."""

from __future__ import annotations

import base64
from typing import Any, cast

from openai import AsyncOpenAI

_DALLE_SIZES = {
    "16:9": "1792x1024",
    "1:1": "1024x1024",
    "9:16": "1024x1792",
}


class OpenAIImage:
    name = "dalle"

    def __init__(self, *, api_key: str, model: str = "dall-e-3") -> None:
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate(self, *, prompt: str, aspect_ratio: str) -> bytes:
        size = _DALLE_SIZES.get(aspect_ratio, "1024x1024")
        resp = await self._client.images.generate(
            model=self.model,
            prompt=prompt,
            size=cast(Any, size),
            response_format="b64_json",
            quality="standard",
            n=1,
        )
        data = resp.data or []
        if not data:
            raise RuntimeError("image generation returned no data")
        b64 = data[0].b64_json or ""
        return base64.b64decode(b64)
