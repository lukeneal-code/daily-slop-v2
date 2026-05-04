"""Graph topology tests using the FAKE_LLM clients with a scripted queue.

These cover the three paths the plan specifically calls out:
  - happy path (Elle approves first try)
  - pushback (Elle rejects → writer pushes back → Elle approves)
  - high-severity reject (Elle stays at severity=high through pushback + revision)
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from app.agents.graph import build_graph, make_initial_state
from app.agents.state import Draft, EditorVerdict, SourceRef
from app.config import get_settings
from app.llm.fake import FakeEditor, FakeImage, FakeWriter, reset_script, set_script


@pytest.fixture(autouse=True)
def _local_images_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGES_LOCAL_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("IMAGES_PUBLIC_BASE_URL", "http://test/images")
    get_settings.cache_clear()
    try:
        yield tmp_path / "images"
    finally:
        get_settings.cache_clear()
        # Restore the conftest env so other tests aren't affected.
        os.environ.pop("IMAGES_LOCAL_DIR", None)
        os.environ.pop("IMAGES_PUBLIC_BASE_URL", None)


def _src() -> SourceRef:
    return SourceRef(
        id=1,
        external_id="bbc:abc123",
        outlet="BBC",
        title="Chancellor announces fuel duty rise",
        description="Detail.",
        body_text="",
        url="https://example.com/x",
        section="politics",
    )


def _draft(headline: str = "PUNCHY HEADLINE") -> Draft:
    return Draft(
        headline=headline,
        subheadline="A wry sub.",
        body_html="<p>body</p>",
        image_description="A figure shrugging.",
    )


def _verdict(
    decision: str = "approve", severity: str = "low", score: float = 8.0, notes: str = ""
) -> EditorVerdict:
    return EditorVerdict(
        decision=decision,  # type: ignore[typeddict-item]
        severity=severity,  # type: ignore[typeddict-item]
        score=score,
        notes=notes,
    )


@pytest.fixture(autouse=True)
def _clear_script():
    reset_script()
    yield
    reset_script()


def _graph():
    return build_graph(
        writers={"nigel": FakeWriter("nigel"), "steve": FakeWriter("steve")},
        editor=FakeEditor(),
        image_client=FakeImage(),
    )


@pytest.mark.asyncio
async def test_graph_happy_path_publishes_first_try() -> None:
    set_script(
        drafts=[_draft("HAPPY HEADLINE")],
        verdicts=[_verdict(decision="approve", score=8.5)],
    )
    state = make_initial_state(
        run_id="r1", publish_date=date(2026, 5, 3), source=_src(), writer="nigel"
    )
    out = await _graph().ainvoke(state)

    assert out["status"] == "published"
    assert out["final_draft"]["headline"] == "HAPPY HEADLINE"
    assert out["pushback_used"] is False
    assert out["revision_count"] == 0
    assert out["image"]["aspect_ratio"] == "1:1"
    assert out["image"]["public_url"].endswith(".png")
    assert len(out["editor_history"]) == 1


@pytest.mark.asyncio
async def test_graph_pushback_then_approve_keeps_original_draft() -> None:
    set_script(
        drafts=[_draft("CONTROVERSIAL")],
        verdicts=[
            _verdict(decision="revise", severity="low", score=5.0, notes="thin gag"),
            _verdict(decision="approve", severity="low", score=7.0, notes="ok ok"),
        ],
        pushback_arguments=["The deadpan IS the joke."],
    )
    state = make_initial_state(
        run_id="r2", publish_date=date(2026, 5, 3), source=_src(), writer="nigel"
    )
    out = await _graph().ainvoke(state)

    assert out["status"] == "published"
    assert out["pushback_used"] is True
    assert out["revision_count"] == 0
    # Final draft should be the original — pushback path doesn't rewrite.
    assert out["final_draft"]["headline"] == "CONTROVERSIAL"
    assert len(out["editor_history"]) == 2


@pytest.mark.asyncio
async def test_graph_pushback_then_revise_then_approve_with_concerns() -> None:
    """Editor stays revise after pushback → writer revises once → published with concerns."""
    set_script(
        drafts=[_draft("ORIGINAL"), _draft("REVISED")],
        verdicts=[
            _verdict(decision="revise", severity="medium", score=4.0, notes="tone-deaf"),
            _verdict(decision="revise", severity="medium", score=4.0, notes="still off"),
            _verdict(decision="revise", severity="low", score=5.5, notes="fine, ship it"),
        ],
        pushback_arguments=["Trust the joke."],
    )
    state = make_initial_state(
        run_id="r3", publish_date=date(2026, 5, 3), source=_src(), writer="nigel"
    )
    out = await _graph().ainvoke(state)

    # After pushback didn't move Elle, writer revised once. revision_count==1, severity!=high.
    # Per plan: revise + revision_count>=1 + severity!=high → publish with concerns.
    assert out["status"] == "approved_with_concerns"
    assert out["pushback_used"] is True
    assert out["revision_count"] == 1
    assert out["final_draft"]["headline"] == "REVISED"
    assert len(out["editor_history"]) == 3


@pytest.mark.asyncio
async def test_graph_high_severity_rejects_after_pushback_and_revision() -> None:
    set_script(
        drafts=[_draft("RISKY"), _draft("RISKY-V2")],
        verdicts=[
            _verdict(decision="revise", severity="high", score=2.0, notes="punching down"),
            _verdict(decision="revise", severity="high", score=2.0, notes="still ugly"),
            _verdict(decision="revise", severity="high", score=2.0, notes="kill it"),
        ],
        pushback_arguments=["The piece works."],
    )
    state = make_initial_state(
        run_id="r4", publish_date=date(2026, 5, 3), source=_src(), writer="steve"
    )
    out = await _graph().ainvoke(state)

    assert out["status"] == "rejected"
    assert out["pushback_used"] is True
    assert out["revision_count"] == 1
    # No image is generated for rejected articles.
    assert out.get("image") is None
    assert "kill it" in (out.get("error") or "")
