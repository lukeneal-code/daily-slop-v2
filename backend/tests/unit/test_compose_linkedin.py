from datetime import date
from types import SimpleNamespace

from app.social.compose import LINKEDIN_MAX_COMMENTARY, compose_post


def _art(id_: int, headline: str, section: str = "politics"):
    return SimpleNamespace(
        id=id_, headline=headline, section=section, publish_date=date(2026, 5, 4)
    )


def test_compose_post_contains_all_three_headlines() -> None:
    picks = {
        "headline": _art(1, "FREDDIE STARR ATE MY HAMSTER"),
        "small_1": _art(2, "PM admits 'oven-ready' was always a metaphor"),
        "small_2": _art(3, "Wetherspoons unveils AI bouncer"),
    }
    text = compose_post(picks, site_url="https://dailyslop.co.uk")
    assert text.startswith("In the news today...")
    assert "FREDDIE STARR ATE MY HAMSTER" in text
    assert "PM admits 'oven-ready' was always a metaphor" in text
    assert "Wetherspoons unveils AI bouncer" in text
    assert text.rstrip().endswith("https://dailyslop.co.uk")


def test_compose_post_uses_bullets() -> None:
    picks = {"headline": _art(1, "Headline A"), "small_1": _art(2, "Headline B")}
    text = compose_post(picks, site_url="https://dailyslop.co.uk")
    assert text.count("•") == 2


def test_compose_post_truncates_overlong_input() -> None:
    long_headline = "X" * (LINKEDIN_MAX_COMMENTARY + 100)
    picks = {"headline": _art(1, long_headline)}
    text = compose_post(picks, site_url="https://dailyslop.co.uk")
    assert len(text) <= LINKEDIN_MAX_COMMENTARY


def test_compose_post_with_just_headline_works() -> None:
    picks = {"headline": _art(1, "Only one today")}
    text = compose_post(picks, site_url="https://dailyslop.co.uk")
    assert "Only one today" in text


def test_compose_post_drops_unknown_slots() -> None:
    picks = {
        "headline": _art(1, "A"),
        "weird_slot": _art(99, "should be ignored"),
        "small_1": _art(2, "B"),
    }
    text = compose_post(picks, site_url="https://dailyslop.co.uk")
    assert "should be ignored" not in text
    assert "A" in text and "B" in text
