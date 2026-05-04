"""Anthropic-backed writer (Nigel)."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from app.agents.prompts.loader import render
from app.agents.state import Draft, SourceRef
from app.llm.parse import parse_draft

_LENGTH_HINTS = {
    "headline": "This is the LEAD STORY. Write 3-4 substantial paragraphs.",
    "section": "This is a SECTION article. Write 2-3 punchy paragraphs.",
}


class ClaudeWriter:
    name = "nigel"

    def __init__(self, *, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)

    async def write(self, source: SourceRef, *, slot_hint: str = "section") -> Draft:
        prompt = render(
            "nigel.md",
            section=source["section"],
            length=_LENGTH_HINTS.get(slot_hint, _LENGTH_HINTS["section"]),
            outlet=source["outlet"],
            title=source["title"],
            description=source["description"] or "",
            body_block=(
                f"- Body excerpt: \"{source['body_text']}\""
                if source.get("body_text")
                else ""
            ),
        )
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in message.content if b.type == "text")
        return parse_draft(text)

    async def revise(
        self,
        source: SourceRef,
        previous: Draft,
        editor_notes: str,
        *,
        slot_hint: str = "section",
    ) -> Draft:
        original = render(
            "nigel.md",
            section=source["section"],
            length=_LENGTH_HINTS.get(slot_hint, _LENGTH_HINTS["section"]),
            outlet=source["outlet"],
            title=source["title"],
            description=source["description"] or "",
            body_block=(
                f"- Body excerpt: \"{source['body_text']}\""
                if source.get("body_text")
                else ""
            ),
        )
        revision_addendum = (
            "\n\nThe editor returned the previous draft with these notes:\n"
            f"\"{editor_notes}\"\n\n"
            "PREVIOUS DRAFT:\n"
            f"- Headline: \"{previous['headline']}\"\n"
            f"- Subheadline: \"{previous['subheadline']}\"\n"
            f"- Body: {previous['body_html']}\n\n"
            "Rewrite to address the notes. Keep the same JSON shape."
        )
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": original + revision_addendum}],
        )
        text = "".join(b.text for b in message.content if b.type == "text")
        return parse_draft(text)

    async def respond_to_pushback(
        self, source: SourceRef, previous: Draft, editor_notes: str
    ) -> str:
        prompt = (
            "You are Nigel. Your editor wants a revision but you believe the piece is "
            "right as-is. Argue for keeping it in TWO SENTENCES MAX. Be direct, "
            "British, and specific about the joke or angle the editor missed. "
            "No preamble, no JSON — just the argument.\n\n"
            f"EDITOR NOTES: \"{editor_notes}\"\n"
            f"YOUR DRAFT HEADLINE: \"{previous['headline']}\"\n"
            f"YOUR DRAFT BODY: {previous['body_html']}\n"
        )
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in message.content if b.type == "text").strip()
