from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.scraping.select import select_candidates

NOW = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)


def _src(**kwargs):
    defaults = {
        "id": 0,
        "outlet": "BBC",
        "section": "politics",
        "used": False,
        "fetch_failed": False,
        "published_at": NOW - timedelta(hours=1),
    }
    return SimpleNamespace(**{**defaults, **kwargs})


def test_select_picks_top_k_distinct_outlets() -> None:
    pool = [
        _src(id=1, outlet="BBC"),
        _src(id=2, outlet="Guardian"),
        _src(id=3, outlet="BBC"),
        _src(id=4, outlet="Sky"),
    ]

    chosen = select_candidates(pool, k=3, now=NOW)

    assert {s.id for s in chosen} == {1, 2, 4}


def test_select_skips_used_or_failed() -> None:
    pool = [
        _src(id=1, outlet="BBC", used=True),
        _src(id=2, outlet="Guardian", fetch_failed=True),
        _src(id=3, outlet="Sky"),
    ]
    chosen = select_candidates(pool, k=3, now=NOW)
    assert [s.id for s in chosen] == [3]


def test_select_drops_stale_articles_outside_recency_window() -> None:
    pool = [
        _src(id=1, outlet="BBC", published_at=NOW - timedelta(hours=72)),
        _src(id=2, outlet="Guardian", published_at=NOW - timedelta(hours=10)),
    ]
    chosen = select_candidates(pool, k=3, now=NOW, recency_hours=48)
    assert [s.id for s in chosen] == [2]


def test_select_falls_back_to_same_outlet_when_diversity_runs_out() -> None:
    pool = [
        _src(id=1, outlet="BBC", published_at=NOW - timedelta(hours=1)),
        _src(id=2, outlet="BBC", published_at=NOW - timedelta(hours=2)),
        _src(id=3, outlet="BBC", published_at=NOW - timedelta(hours=3)),
    ]
    chosen = select_candidates(pool, k=3, now=NOW)
    assert [s.id for s in chosen] == [1, 2, 3]
