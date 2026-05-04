"""LangGraph state machine for the per-article generation pipeline.

Topology:

    START
      ↓
    write
      ↓
    edit  ── approve ──→ image_gen → END
      │
      ├── revise + !pushback_used  ──→ pushback_node ──→ edit
      │
      ├── revise + pushback_used + revision_count==0  ──→ revise_node ──→ edit
      │
      └── revise + revision_count≥1
                ├── severity != high  ──→ approve_with_concerns ──→ image_gen → END
                └── severity == high  ──→ END (status=rejected)

`revise` after a pushback bumps `revision_count`. `approve` short-circuits to
image generation. The "she gets the final word" path is `revision_count >= 1` —
either the latest draft is published with Elle's note logged, or it's killed.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.state import (
    Draft,
    EditorVerdict,
    GeneratedImage,
    PipelineState,
    SourceRef,
    WriterId,
)
from app.images.prompts import build_prompt
from app.images.storage import store_image
from app.llm.base import EditorClient, ImageClient, WriterClient
from app.observability.langfuse import trace_node
from app.utils.slug import base_slug

log = logging.getLogger(__name__)


def _writer_for(state: PipelineState, writers: dict[str, WriterClient]) -> WriterClient:
    return writers[state["writer"]]


def _slot_hint(state: PipelineState) -> str:
    # The orchestrator marks the lead candidate per section by tagging the source
    # with `slot_hint = "headline"`. Default to "section".
    return "section"


def _build_write_node(
    writers: dict[str, WriterClient],
) -> Callable[[PipelineState], Awaitable[PipelineState]]:
    async def write(state: PipelineState) -> PipelineState:
        writer = _writer_for(state, writers)
        previous = state.get("draft")
        verdict = state.get("editor_verdict")
        if previous and verdict and verdict["decision"] == "revise":
            new_draft = await writer.revise(
                state["source"], previous, verdict["notes"], slot_hint=_slot_hint(state)
            )
            return {
                **state,
                "draft": new_draft,
                "revision_count": state.get("revision_count", 0) + 1,
            }
        new_draft = await writer.write(state["source"], slot_hint=_slot_hint(state))
        return {
            **state,
            "draft": new_draft,
            "revision_count": state.get("revision_count", 0),
            "pushback_used": state.get("pushback_used", False),
            "editor_history": state.get("editor_history", []),
        }

    return write


def _build_edit_node(
    editor: EditorClient,
) -> Callable[[PipelineState], Awaitable[PipelineState]]:
    async def edit(state: PipelineState) -> PipelineState:
        draft = state["draft"]
        assert draft is not None
        if state.get("pushback_argument") and state.get("editor_verdict"):
            verdict = await editor.review_after_pushback(
                state["source"],
                draft,
                state["writer"],
                state["editor_verdict"]["notes"],  # type: ignore[index]
                state["pushback_argument"] or "",
            )
        else:
            verdict = await editor.review(state["source"], draft, state["writer"])
        history = list(state.get("editor_history", []))
        history.append(verdict)
        return {
            **state,
            "editor_verdict": verdict,
            "editor_history": history,
            "pushback_argument": None,
        }

    return edit


def _build_pushback_node(
    writers: dict[str, WriterClient],
) -> Callable[[PipelineState], Awaitable[PipelineState]]:
    async def pushback(state: PipelineState) -> PipelineState:
        writer = _writer_for(state, writers)
        verdict = state["editor_verdict"]
        draft = state["draft"]
        assert verdict is not None and draft is not None
        argument = await writer.respond_to_pushback(
            state["source"], draft, verdict["notes"]
        )
        return {**state, "pushback_used": True, "pushback_argument": argument}

    return pushback


def _build_image_node(
    image_client: ImageClient,
) -> Callable[[PipelineState], Awaitable[PipelineState]]:
    async def image_gen(state: PipelineState) -> PipelineState:
        final = state.get("draft")
        assert final is not None
        aspect = "16:9" if _slot_hint(state) == "headline" else "1:1"
        prompt = build_prompt(final["image_description"])
        publish_date_v: date = state["publish_date"]
        slug = base_slug(final["headline"])

        verdict = state.get("editor_verdict")
        status: Literal["published", "approved_with_concerns"] = (
            "approved_with_concerns"
            if verdict and verdict["decision"] == "revise"
            else "published"
        )

        # Image generation can fail on content-policy violations (DALL-E sometimes
        # rejects satirical prompts even after Elle's review). When that happens,
        # publish the article without an image rather than killing the run.
        image: GeneratedImage | None = None
        try:
            data = await image_client.generate(prompt=prompt, aspect_ratio=aspect)
            stored = await store_image(
                data=data, publish_date=publish_date_v, slug=slug, aspect_ratio=aspect
            )
            image = {
                "public_url": stored.public_url,
                "gcs_uri": stored.gcs_uri,
                "prompt": prompt,
                "width": stored.width,
                "height": stored.height,
                "aspect_ratio": aspect,
                "image_alt": final["image_description"][:200],
            }
        except Exception as exc:
            log.warning(
                "image_gen failed for run=%s section=%s slug=%s: %s",
                state.get("run_id"),
                state.get("section"),
                slug,
                exc,
            )

        return {**state, "final_draft": final, "image": image, "status": status}

    return image_gen


async def _reject_node(state: PipelineState) -> PipelineState:
    verdict = state.get("editor_verdict")
    return {
        **state,
        "status": "rejected",
        "error": verdict["notes"] if verdict else "rejected",
    }


def _route_after_edit(state: PipelineState) -> str:
    verdict: EditorVerdict | None = state.get("editor_verdict")
    if verdict is None:
        # Defensive — shouldn't happen.
        return "image_gen"
    if verdict["decision"] == "approve":
        return "image_gen"
    revision_count = state.get("revision_count", 0)
    pushback_used = state.get("pushback_used", False)
    if not pushback_used:
        return "pushback"
    if revision_count < 1:
        return "write"
    if verdict["severity"] == "high":
        return "reject"
    return "image_gen"


def build_graph(
    *,
    writers: dict[str, WriterClient],
    editor: EditorClient,
    image_client: ImageClient,
) -> Any:
    # The LangGraph StateGraph generic doesn't compose cleanly with closures returning
    # `Awaitable[PipelineState]`. We type the builder dynamically; behaviour is
    # exercised by tests/unit/test_graph.py.
    g: Any = StateGraph(PipelineState)

    g.add_node("write", trace_node("write")(_build_write_node(writers)))
    g.add_node("edit", trace_node("edit")(_build_edit_node(editor)))
    g.add_node("pushback", trace_node("pushback")(_build_pushback_node(writers)))
    g.add_node("image_gen", trace_node("image_gen")(_build_image_node(image_client)))
    g.add_node("reject", trace_node("reject")(_reject_node))

    g.add_edge(START, "write")
    g.add_edge("write", "edit")
    g.add_conditional_edges(
        "edit",
        _route_after_edit,
        {
            "image_gen": "image_gen",
            "pushback": "pushback",
            "write": "write",
            "reject": "reject",
        },
    )
    g.add_edge("pushback", "edit")
    g.add_edge("image_gen", END)
    g.add_edge("reject", END)
    return g.compile()


def make_initial_state(
    *,
    run_id: str,
    publish_date: date,
    source: SourceRef,
    writer: WriterId,
) -> PipelineState:
    return {
        "run_id": run_id,
        "publish_date": publish_date,
        "section": source["section"],
        "source": source,
        "writer": writer,
        "draft": None,
        "revision_count": 0,
        "pushback_used": False,
        "pushback_argument": None,
        "editor_verdict": None,
        "editor_history": [],
        "final_draft": None,
        "image": None,
    }


__all__ = ["build_graph", "make_initial_state", "PipelineState", "Draft"]
