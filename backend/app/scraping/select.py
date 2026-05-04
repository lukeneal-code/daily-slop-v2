"""Pick `k` candidate stories per section from the source pool.

Diversity rules:
- Prefer different outlets when possible.
- Prefer recent items (`published_at` within the last `recency_hours`).
- Skip items already marked `used = true`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from app.db.models import SourceArticle


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def select_candidates(
    pool: Iterable[SourceArticle],
    *,
    k: int = 3,
    now: datetime | None = None,
    recency_hours: int = 48,
) -> list[SourceArticle]:
    now = _aware(now or datetime.now(UTC))
    cutoff = now - timedelta(hours=recency_hours)
    pool_sorted = sorted(
        (
            s
            for s in pool
            if not s.used
            and not s.fetch_failed
            and (s.published_at is None or _aware(s.published_at) >= cutoff)
        ),
        key=lambda s: _aware(s.published_at) if s.published_at else datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    chosen: list[SourceArticle] = []
    seen_outlets: set[str] = set()

    for s in pool_sorted:
        if s.outlet not in seen_outlets:
            chosen.append(s)
            seen_outlets.add(s.outlet)
        if len(chosen) >= k:
            return chosen

    # Fall back to filling slots regardless of outlet diversity.
    for s in pool_sorted:
        if s in chosen:
            continue
        chosen.append(s)
        if len(chosen) >= k:
            break

    return chosen
