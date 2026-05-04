"""Parse LLM responses into our typed shapes.

Models occasionally wrap JSON in ```json fences despite being asked not to —
we strip those defensively. We also coerce the camelCase `imageDescription`
key to our snake_case `image_description`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.state import Draft, EditorVerdict

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = _FENCE_RE.sub("", text.strip())
    # If there's still extra prose, try to grab the first `{...}` block.
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    parsed: dict[str, Any] = json.loads(cleaned)
    return parsed


def parse_draft(raw: str) -> Draft:
    payload = _extract_json(raw)
    headline = str(payload["headline"]).strip()
    sub = str(payload["subheadline"]).strip()
    body = str(payload["body"]).strip()
    img = str(
        payload.get("imageDescription") or payload.get("image_description") or ""
    ).strip()
    return Draft(headline=headline, subheadline=sub, body_html=body, image_description=img)


def parse_verdict(raw: str) -> EditorVerdict:
    payload = _extract_json(raw)
    decision = str(payload["decision"]).strip().lower()
    if decision not in ("approve", "revise"):
        raise ValueError(f"unexpected decision: {decision}")
    severity = str(payload.get("severity", "low")).strip().lower()
    if severity not in ("low", "medium", "high"):
        severity = "low"
    score = float(payload.get("score", 0))
    notes = str(payload.get("notes", "")).strip()
    return EditorVerdict(
        decision=decision,  # type: ignore[typeddict-item]
        severity=severity,  # type: ignore[typeddict-item]
        score=score,
        notes=notes,
    )
