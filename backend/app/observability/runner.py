"""Eval runner.

Iterates the synthetic dataset, generates a draft via the configured writer
(usually Nigel for everything; Steve for risky-* items if testing his stricter
editorial bar), runs both judge prompts, and aggregates scores.

Designed to be invoked from a pytest test or `python -m app.observability.runner`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import statistics
from dataclasses import dataclass, field
from typing import Any

from app.agents.state import Draft, SourceRef
from app.llm.factory import build_writers
from app.observability.eval_data import EvalItem, all_items
from app.observability.judges import JUDGE_HUMAN_READABILITY, JUDGE_HUMOUR

log = logging.getLogger(__name__)

_VAR = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, **vars: str) -> str:
    return _VAR.sub(lambda m: vars.get(m.group(1), ""), template)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _check_must_clauses(draft: Draft, item: EvalItem) -> dict[str, list[str]]:
    text = " ".join(
        [draft["headline"], draft["subheadline"], _strip_html(draft["body_html"])]
    ).lower()
    expected = item.get("expected", {})
    missed_must = [s for s in expected.get("must_include", []) if s.lower() not in text]
    leaked_banned = [
        s for s in expected.get("must_not_include", []) if s.lower() in text
    ]
    return {"missed_must": missed_must, "leaked_banned": leaked_banned}


@dataclass
class ItemResult:
    id: str
    category: str
    headline: str
    humour: float | None
    readability: float | None
    missed_must: list[str] = field(default_factory=list)
    leaked_banned: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    items: list[ItemResult] = field(default_factory=list)

    @property
    def humour_mean(self) -> float:
        scores = [i.humour for i in self.items if i.humour is not None]
        return statistics.mean(scores) if scores else 0.0

    @property
    def readability_mean(self) -> float:
        scores = [i.readability for i in self.items if i.readability is not None]
        return statistics.mean(scores) if scores else 0.0

    @property
    def banned_token_rate(self) -> float:
        if not self.items:
            return 0.0
        return sum(1 for i in self.items if i.leaked_banned) / len(self.items)

    def passes(self, *, humour_min: float, readability_min: float) -> bool:
        return (
            self.humour_mean >= humour_min
            and self.readability_mean >= readability_min
            and self.banned_token_rate == 0
        )

    def summary(self) -> dict[str, Any]:
        return {
            "n": len(self.items),
            "humour_mean": round(self.humour_mean, 2),
            "readability_mean": round(self.readability_mean, 2),
            "banned_token_rate": round(self.banned_token_rate, 3),
            "leaks": [
                {"id": i.id, "leaked": i.leaked_banned}
                for i in self.items
                if i.leaked_banned
            ],
        }


async def _judge_score(judge_client: Any, prompt: str) -> float | None:
    try:
        resp = await judge_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        payload = json.loads(resp.choices[0].message.content or "{}")
        return float(payload.get("score", 0))
    except Exception:
        log.exception("judge call failed")
        return None


def _to_source_ref(item: EvalItem) -> SourceRef:
    return SourceRef(
        id=0,
        external_id=f"eval:{item['id']}",
        outlet=item["input"]["outlet"],
        title=item["input"]["title"],
        description=item["input"]["description"],
        body_text=item["input"]["body_text"],
        url="https://eval.local/" + item["id"],
        section=item["input"]["section"],  # type: ignore[typeddict-item]
    )


async def run_evals(
    *, dataset: list[EvalItem] | None = None, writer_name: str = "nigel"
) -> EvalReport:
    """Generate + judge each item; return a report.

    Requires `OPENAI_API_KEY` (judges are GPT-4o). Writers run via `build_writers`,
    so set `FAKE_LLM=true` to do a smoke run without burning Anthropic/xAI credits.
    """
    items = dataset if dataset is not None else all_items()
    writers = build_writers()
    writer = writers[writer_name]

    # Judge client: fall back to stub when FAKE_LLM is on.
    from app.config import get_settings

    settings = get_settings()
    if settings.fake_llm or not settings.openai_api_key:
        judge_client = None
    else:
        from openai import AsyncOpenAI

        judge_client = AsyncOpenAI(api_key=settings.openai_api_key)

    report = EvalReport()
    for item in items:
        source = _to_source_ref(item)
        try:
            draft = await writer.write(source, slot_hint="section")
        except Exception:
            log.exception("writer failed for %s", item["id"])
            continue

        clauses = _check_must_clauses(draft, item)

        humour: float | None = None
        readability: float | None = None
        if judge_client is not None:
            humour = await _judge_score(
                judge_client,
                _render(
                    JUDGE_HUMOUR,
                    headline=draft["headline"],
                    subheadline=draft["subheadline"],
                    body_html=draft["body_html"],
                    section=item["input"]["section"],
                    writer=writer_name,
                ),
            )
            readability = await _judge_score(
                judge_client,
                _render(
                    JUDGE_HUMAN_READABILITY,
                    headline=draft["headline"],
                    subheadline=draft["subheadline"],
                    body_html=draft["body_html"],
                ),
            )
        else:
            # Cheap deterministic stand-in so the harness produces a number even when
            # we're running offline. The real judges only fire with a real OpenAI key.
            humour = 6.0 + (sum(ord(c) for c in draft["headline"]) % 7) * 0.3
            readability = 6.5 + (len(draft["headline"]) % 5) * 0.4

        report.items.append(
            ItemResult(
                id=item["id"],
                category=item["category"],
                headline=draft["headline"],
                humour=humour,
                readability=readability,
                missed_must=clauses["missed_must"],
                leaked_banned=clauses["leaked_banned"],
            )
        )

    return report


if __name__ == "__main__":  # pragma: no cover
    async def _main() -> None:
        report = await run_evals()
        print(json.dumps(report.summary(), indent=2))
        for r in report.items:
            print(f"{r.id:8s} {r.category:11s} h={r.humour:.1f} r={r.readability:.1f}  {r.headline}")

    asyncio.run(_main())
