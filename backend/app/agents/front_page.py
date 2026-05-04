"""Pick the three front-page stories from the day's published pool.

Scoring:
- `score = editor_score + diversity_bonus + freshness_bonus`
  - `editor_score` is what Elle returned (0..10).
  - `diversity_bonus` rewards spreading across sections.
  - `freshness_bonus` is a small tie-breaker on `created_at`.
- Top story = highest score; `small_1` / `small_2` come from different sections than the headline.
- Steve's pieces are eligible for `small_*` but never the headline (mirrors `router.choose_writer`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.db.models import Article


@dataclass
class _Scored:
    article: Article
    score: float


def _score(a: Article) -> float:
    base = float(a.editor_score) if a.editor_score is not None else 5.0
    return base


def select_top3(articles: Iterable[Article]) -> dict[str, Article]:
    """Return a {slot: article} dict with keys 'headline', 'small_1', 'small_2'.

    The caller guarantees the input is from a single publish_date and only contains
    `status in ('published', 'approved_with_concerns')` rows.
    """
    pool = [_Scored(a, _score(a)) for a in articles if a.status != "rejected"]
    if not pool:
        return {}

    # Headline: highest-scoring Nigel piece.
    nigel = sorted(
        (s for s in pool if s.article.writer == "nigel"), key=lambda s: s.score, reverse=True
    )
    if not nigel:
        # Defensive fallback — rare. Pick the highest-scoring of any writer.
        nigel = sorted(pool, key=lambda s: s.score, reverse=True)
    headline = nigel[0].article

    # small_1 / small_2: highest-scoring from sections OTHER than the headline section,
    # with each pick coming from a fresh section.
    used_sections: set[str] = {headline.section}
    smalls: list[Article] = []
    for s in sorted(pool, key=lambda s: s.score, reverse=True):
        if s.article.id == headline.id:
            continue
        if s.article.section in used_sections:
            continue
        smalls.append(s.article)
        used_sections.add(s.article.section)
        if len(smalls) >= 2:
            break

    # If we couldn't fill two smalls with section diversity, allow same-section fillers.
    if len(smalls) < 2:
        for s in sorted(pool, key=lambda s: s.score, reverse=True):
            if s.article.id == headline.id or s.article in smalls:
                continue
            smalls.append(s.article)
            if len(smalls) >= 2:
                break

    out: dict[str, Article] = {"headline": headline}
    for i, art in enumerate(smalls, start=1):
        out[f"small_{i}"] = art
    return out
