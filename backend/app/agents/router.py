"""Decide which writer (`nigel` | `steve`) covers a given source story.

Rules:
- Steve never gets `royals` (libel/brand risk).
- Steve never gets stories destined for the front-page headline slot.
- Otherwise, Steve gets ~`steve_quota` of stories, deterministic by external_id
  so re-running the pipeline picks the same writer.
"""

from __future__ import annotations

import hashlib

from app.agents.state import SectionSlug, SourceRef, WriterId


def _hash_bucket(external_id: str, buckets: int) -> int:
    h = hashlib.sha1(external_id.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % buckets


def choose_writer(
    source: SourceRef,
    *,
    steve_quota: float = 0.25,
    is_headline_candidate: bool = False,
) -> WriterId:
    if source["section"] == "royals":
        return "nigel"
    if is_headline_candidate:
        return "nigel"
    if steve_quota <= 0:
        return "nigel"
    if steve_quota >= 1:
        return "steve"
    # Bucket count = 1 / quota, rounded. Bucket 0 → Steve.
    buckets = max(2, round(1 / steve_quota))
    return "steve" if _hash_bucket(source["external_id"], buckets) == 0 else "nigel"


def steve_eligible_sections() -> tuple[SectionSlug, ...]:
    return ("politics", "business", "tech", "culture", "sport")
