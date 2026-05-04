"""LangGraph state shape for the daily article pipeline.

The graph processes one (section, source) pair per invocation. The daily orchestrator
in `pipeline/daily.py` runs many graph invocations concurrently and then ranks the
results for front-page placement.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, TypedDict

WriterId = Literal["nigel", "steve"]
SectionSlug = Literal["politics", "business", "tech", "culture", "sport", "royals"]
EditorDecision = Literal["approve", "revise"]
Severity = Literal["low", "medium", "high"]


class SourceRef(TypedDict):
    id: int
    external_id: str
    outlet: str
    title: str
    description: str
    body_text: str
    url: str
    section: SectionSlug


class Draft(TypedDict):
    headline: str
    subheadline: str
    body_html: str
    image_description: str


class EditorVerdict(TypedDict):
    decision: EditorDecision
    severity: Severity
    score: float  # 0..10
    notes: str


class GeneratedImage(TypedDict):
    public_url: str
    gcs_uri: str | None
    prompt: str
    width: int
    height: int
    aspect_ratio: str
    image_alt: str


class PipelineState(TypedDict, total=False):
    """LangGraph state. Some keys are filled in by later nodes."""

    run_id: str
    publish_date: date
    section: SectionSlug
    source: SourceRef
    writer: WriterId

    # Writing
    draft: Draft | None
    revision_count: int
    pushback_used: bool
    pushback_argument: str | None

    # Editing
    editor_verdict: EditorVerdict | None
    editor_history: list[EditorVerdict]

    # Final
    final_draft: Draft | None
    image: GeneratedImage | None
    status: Literal["published", "approved_with_concerns", "rejected"]
    error: str | None
