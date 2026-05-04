"""Build the writer/editor/image clients based on settings.

`FAKE_LLM=true` swaps every client for the deterministic test double, so
`docker compose up` works without any API keys. Real keys are read at construction
time so a missing key fails loudly, not silently at first call.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.llm.base import EditorClient, ImageClient, WriterClient
from app.llm.fake import FakeEditor, FakeImage, FakeWriter


def build_writers(settings: Settings | None = None) -> dict[str, WriterClient]:
    s = settings or get_settings()
    if s.fake_llm:
        return {
            "nigel": FakeWriter(name="nigel", model="fake-claude"),
            "steve": FakeWriter(name="steve", model="fake-grok"),
        }
    from app.llm.anthropic_client import ClaudeWriter
    from app.llm.openai_client import XAISteve

    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required when FAKE_LLM=false")
    if not s.xai_api_key:
        raise RuntimeError("XAI_API_KEY required when FAKE_LLM=false")
    return {
        "nigel": ClaudeWriter(api_key=s.anthropic_api_key, model=s.nigel_model),
        "steve": XAISteve(api_key=s.xai_api_key, model=s.steve_model),
    }


def build_editor(settings: Settings | None = None) -> EditorClient:
    s = settings or get_settings()
    if s.fake_llm:
        return FakeEditor(model="fake-gpt")
    from app.llm.openai_client import OpenAIEditor

    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY required when FAKE_LLM=false")
    return OpenAIEditor(api_key=s.openai_api_key, model=s.elle_model)


def build_image(settings: Settings | None = None) -> ImageClient:
    s = settings or get_settings()
    if s.fake_llm:
        return FakeImage(model="fake-dalle")
    from app.llm.openai_client_image import OpenAIImage

    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY required when FAKE_LLM=false")
    return OpenAIImage(api_key=s.openai_api_key, model=s.image_model)
