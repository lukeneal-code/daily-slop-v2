"""Deterministic test doubles for the writer / editor / image clients.

Two operating modes:

1. **Default (no scripting)** — given the same `(writer, source.external_id)`,
   produces stable, plausible-looking outputs. Lets `docker compose up` give a
   working end-to-end demo without API credits.

2. **Scripted** — tests inject a queue of canned outputs via `set_script(...)`.
   Useful for exercising specific graph paths (pushback edge, severity=high reject).
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.agents.state import Draft, EditorVerdict, SourceRef


def _stable_hash(s: str) -> int:
    return int(hashlib.sha1(s.encode("utf-8")).hexdigest()[:8], 16)


def _short_headline(source: SourceRef, writer: str) -> str:
    seed = _stable_hash(f"{writer}:{source['external_id']}") % 5
    base = source["title"].upper()
    suffixes = [
        "; NATION SHRUGS",
        ", SAYS UNNAMED CABINET CAT",
        " — NATION TUTS",
        ", NO ONE NOTICES",
        ", SOMEHOW",
    ]
    truncated = " ".join(base.split()[:6])
    return f"{truncated}{suffixes[seed]}"[:80]


def _fake_draft(source: SourceRef, writer: str) -> Draft:
    headline = _short_headline(source, writer)
    sub = (
        "An exclusive non-investigation reveals nothing of note, but at length, "
        "and with characteristic deadpan."
    )
    body = (
        "<p>In a development that surprised precisely no one, sources close to the matter "
        f"have confirmed that the matter is, in fact, the matter. Officials at "
        f"{source['outlet']} could not be reached, possibly because they were busy.</p>"
        '<p>"This is exactly what we have come to expect," said Felicity Bramble-Whitlow, '
        '57, of Tunbridge Wells, "which is to say nothing at all, but in a slightly '
        'different font."</p>'
        "<p>The Daily Slop will continue to monitor the situation by ignoring it.</p>"
    )
    image_desc = (
        f"A dignified middle-aged figure at a podium labelled '{source['section']}', "
        "shrugging elaborately. Other figures in the wings nod in approval."
    )
    return Draft(
        headline=headline,
        subheadline=sub,
        body_html=body,
        image_description=image_desc,
    )


@dataclass
class _Script:
    drafts: list[Draft] = field(default_factory=list)
    verdicts: list[EditorVerdict] = field(default_factory=list)
    pushback_arguments: list[str] = field(default_factory=list)


_SCRIPT = _Script()


def set_script(
    *,
    drafts: Iterable[Draft] = (),
    verdicts: Iterable[EditorVerdict] = (),
    pushback_arguments: Iterable[str] = (),
) -> None:
    _SCRIPT.drafts = list(drafts)
    _SCRIPT.verdicts = list(verdicts)
    _SCRIPT.pushback_arguments = list(pushback_arguments)


def reset_script() -> None:
    set_script()


class FakeWriter:
    name: str

    def __init__(self, name: str = "nigel", model: str = "fake-claude") -> None:
        self.name = name
        self.model = model

    async def write(self, source: SourceRef, *, slot_hint: str = "section") -> Draft:
        await asyncio.sleep(0)
        if _SCRIPT.drafts:
            return _SCRIPT.drafts.pop(0)
        return _fake_draft(source, self.name)

    async def revise(
        self,
        source: SourceRef,
        previous: Draft,
        editor_notes: str,
        *,
        slot_hint: str = "section",
    ) -> Draft:
        await asyncio.sleep(0)
        if _SCRIPT.drafts:
            return _SCRIPT.drafts.pop(0)
        # Mark as revised so tests can assert.
        return Draft(
            headline=previous["headline"] + " (REVISED)",
            subheadline=previous["subheadline"],
            body_html=previous["body_html"],
            image_description=previous["image_description"],
        )

    async def respond_to_pushback(
        self,
        source: SourceRef,
        previous: Draft,
        editor_notes: str,
    ) -> str:
        await asyncio.sleep(0)
        if _SCRIPT.pushback_arguments:
            return _SCRIPT.pushback_arguments.pop(0)
        return (
            "Respectfully, the joke lands precisely because it's deadpan; "
            "the alternative reads as parody-of-parody."
        )


class FakeEditor:
    name: str = "elle"

    def __init__(self, model: str = "fake-gpt") -> None:
        self.model = model

    async def review(
        self, source: SourceRef, draft: Draft, writer: str
    ) -> EditorVerdict:
        await asyncio.sleep(0)
        if _SCRIPT.verdicts:
            return _SCRIPT.verdicts.pop(0)
        return EditorVerdict(
            decision="approve", severity="low", score=7.5, notes="Reads well."
        )

    async def review_after_pushback(
        self,
        source: SourceRef,
        draft: Draft,
        writer: str,
        previous_notes: str,
        pushback: str,
    ) -> EditorVerdict:
        await asyncio.sleep(0)
        if _SCRIPT.verdicts:
            return _SCRIPT.verdicts.pop(0)
        return EditorVerdict(
            decision="approve",
            severity="low",
            score=7.0,
            notes="Conceded — the writer makes a reasonable case.",
        )


class FakeImage:
    name: str = "fake-image"

    def __init__(self, model: str = "fake-dalle") -> None:
        self.model = model

    async def generate(self, *, prompt: str, aspect_ratio: str) -> bytes:
        await asyncio.sleep(0)
        # Smallest valid PNG (1x1 transparent). Good enough for round-tripping.
        return bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000d49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082"
        )
