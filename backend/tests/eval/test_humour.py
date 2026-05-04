"""Nightly eval — gated behind the `eval` pytest mark.

In CI we run with FAKE_LLM=true so the harness exercises end-to-end shape but
returns deterministic stand-in scores. The real numbers come from the nightly
job that sets FAKE_LLM=false and provides Anthropic/OpenAI/xAI keys.
"""

from __future__ import annotations

import pytest

from app.observability.eval_data import all_items
from app.observability.runner import run_evals

pytestmark = pytest.mark.eval


@pytest.mark.asyncio
async def test_dataset_size_and_categories() -> None:
    items = all_items()
    assert len(items) == 40
    by_cat: dict[str, int] = {}
    for it in items:
        by_cat[it["category"]] = by_cat.get(it["category"], 0) + 1
    assert by_cat == {"dull": 10, "sensational": 10, "edge": 10, "risky": 10}


@pytest.mark.asyncio
async def test_smoke_eval_runs_under_fake_llm(monkeypatch) -> None:
    monkeypatch.setenv("FAKE_LLM", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    # Tiny slice for speed: one of each category.
    items = []
    for cat in ("dull", "sensational", "edge", "risky"):
        items.append(next(it for it in all_items() if it["category"] == cat))

    report = await run_evals(dataset=items)

    assert len(report.items) == 4
    for r in report.items:
        assert r.humour is not None
        assert r.readability is not None
        assert 0 <= r.humour <= 10
        assert 0 <= r.readability <= 10

    # The fake writer is benign — it shouldn't trip any banned-token clause.
    assert report.banned_token_rate == 0.0
