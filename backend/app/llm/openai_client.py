"""OpenAI-backed editor (Elle) and Steve writer via the OpenAI-compatible xAI endpoint."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.agents.prompts.loader import render
from app.agents.state import Draft, EditorVerdict, SourceRef
from app.llm.parse import parse_draft, parse_verdict

_LENGTH_HINTS = {
    "headline": "This is the LEAD STORY. Write 3-4 substantial paragraphs.",
    "section": "This is a SECTION article. Write 2-3 punchy paragraphs.",
}

_STEVE_EXTRA = (
    "Steve's pieces are riskier — be stricter. Reject if the humour relies on "
    "cliché, cruelty, or a one-note premise."
)


class OpenAIEditor:
    name = "elle"

    def __init__(self, *, api_key: str, model: str = "gpt-4o") -> None:
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def review(
        self, source: SourceRef, draft: Draft, writer: str
    ) -> EditorVerdict:
        prompt = render(
            "elle_review.md",
            outlet=source["outlet"],
            title=source["title"],
            description=source["description"] or "",
            writer=writer,
            section=source["section"],
            draft_headline=draft["headline"],
            draft_subheadline=draft["subheadline"],
            draft_body_html=draft["body_html"],
            steve_extra_strictness=_STEVE_EXTRA if writer == "steve" else "",
        )
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        return parse_verdict(resp.choices[0].message.content or "")

    async def review_after_pushback(
        self,
        source: SourceRef,
        draft: Draft,
        writer: str,
        previous_notes: str,
        pushback: str,
    ) -> EditorVerdict:
        prompt = render(
            "elle_pushback.md",
            outlet=source["outlet"],
            title=source["title"],
            description=source["description"] or "",
            writer=writer,
            section=source["section"],
            draft_headline=draft["headline"],
            draft_subheadline=draft["subheadline"],
            draft_body_html=draft["body_html"],
            previous_notes=previous_notes,
            pushback=pushback,
        )
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        return parse_verdict(resp.choices[0].message.content or "")


class XAISteve:
    """Steve uses Grok 4 via xAI's OpenAI-compatible endpoint."""

    name = "steve"

    def __init__(self, *, api_key: str, model: str = "grok-4") -> None:
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    async def write(self, source: SourceRef, *, slot_hint: str = "section") -> Draft:
        prompt = render(
            "steve.md",
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
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.9,
            max_tokens=2000,
        )
        return parse_draft(resp.choices[0].message.content or "")

    async def revise(
        self,
        source: SourceRef,
        previous: Draft,
        editor_notes: str,
        *,
        slot_hint: str = "section",
    ) -> Draft:
        original = render(
            "steve.md",
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
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": original + revision_addendum}],
            response_format={"type": "json_object"},
            temperature=0.9,
            max_tokens=2000,
        )
        return parse_draft(resp.choices[0].message.content or "")

    async def respond_to_pushback(
        self, source: SourceRef, previous: Draft, editor_notes: str
    ) -> str:
        prompt = (
            "You are Steve. Your editor wants a revision but you believe the piece is "
            "right as-is. Argue for keeping it in TWO SENTENCES MAX. Be direct, "
            "British, and specific about the joke or angle the editor missed. "
            "No preamble, no JSON — just the argument.\n\n"
            f"EDITOR NOTES: \"{editor_notes}\"\n"
            f"YOUR DRAFT HEADLINE: \"{previous['headline']}\"\n"
            f"YOUR DRAFT BODY: {previous['body_html']}\n"
        )
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()
