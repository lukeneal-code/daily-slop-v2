"""Thin Protocol-based LLM client interfaces.

The pipeline only ever calls these protocols. Real implementations
(`anthropic_client.py`, `openai_client.py`, `xai_client.py`) and fakes
(`fake.py`) all conform to the same shape, so swapping is just a factory call.
"""

from __future__ import annotations

from typing import Protocol

from app.agents.state import Draft, EditorVerdict, SourceRef


class WriterClient(Protocol):
    name: str
    model: str

    async def write(self, source: SourceRef, *, slot_hint: str = "section") -> Draft: ...

    async def revise(
        self,
        source: SourceRef,
        previous: Draft,
        editor_notes: str,
        *,
        slot_hint: str = "section",
    ) -> Draft: ...

    async def respond_to_pushback(
        self,
        source: SourceRef,
        previous: Draft,
        editor_notes: str,
    ) -> str:
        """Return the writer's argument for keeping the draft as-is (max 2 sentences)."""
        ...


class EditorClient(Protocol):
    name: str
    model: str

    async def review(self, source: SourceRef, draft: Draft, writer: str) -> EditorVerdict: ...

    async def review_after_pushback(
        self,
        source: SourceRef,
        draft: Draft,
        writer: str,
        previous_notes: str,
        pushback: str,
    ) -> EditorVerdict: ...


class ImageClient(Protocol):
    name: str
    model: str

    async def generate(self, *, prompt: str, aspect_ratio: str) -> bytes: ...
