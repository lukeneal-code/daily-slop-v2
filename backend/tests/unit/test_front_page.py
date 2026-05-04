from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.agents.front_page import select_top3


def _art(
    id_: int,
    *,
    section: str,
    score: float,
    writer: str = "nigel",
    status: str = "published",
):
    return SimpleNamespace(
        id=id_,
        section=section,
        editor_score=Decimal(str(score)),
        writer=writer,
        status=status,
        publish_date=date(2026, 5, 3),
    )


def test_top3_picks_highest_nigel_for_headline_then_diverse_smalls() -> None:
    pool = [
        _art(1, section="politics", score=8.0),
        _art(2, section="business", score=7.5),
        _art(3, section="tech", score=9.5),  # Steve = ineligible for headline
        _art(4, section="tech", score=6.0),
    ]
    pool[2].writer = "steve"

    picks = select_top3(pool)
    assert picks["headline"].id == 1, "highest-scoring Nigel should be the headline"
    # smalls should come from sections OTHER than the headline section.
    assert picks["small_1"].section != "politics"
    assert picks["small_2"].section != "politics"
    # Steve is eligible for smalls.
    smalls_ids = {picks["small_1"].id, picks["small_2"].id}
    assert 3 in smalls_ids


def test_top3_skips_rejected_articles() -> None:
    pool = [
        _art(1, section="politics", score=9.0, status="rejected"),
        _art(2, section="business", score=7.0),
        _art(3, section="tech", score=6.0),
    ]
    picks = select_top3(pool)
    assert picks["headline"].id == 2


def test_top3_falls_back_to_same_section_when_diversity_runs_out() -> None:
    pool = [
        _art(1, section="politics", score=9.0),
        _art(2, section="politics", score=8.5),
    ]
    picks = select_top3(pool)
    assert picks["headline"].id == 1
    # Only one other story exists, and it's the same section — must still appear.
    assert picks["small_1"].id == 2
    assert "small_2" not in picks
