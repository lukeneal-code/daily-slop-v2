"""Build the LinkedIn commentary string from the day's front-page picks."""

from __future__ import annotations

from collections.abc import Iterable

from app.db.models import Article

LINKEDIN_MAX_COMMENTARY = 3000
SLOTS_IN_ORDER = ("headline", "small_1", "small_2")


def ordered_picks(picks: dict[str, Article]) -> list[Article]:
    """Return picks in display order, dropping missing slots."""
    return [picks[slot] for slot in SLOTS_IN_ORDER if slot in picks]


def compose_post(picks: dict[str, Article], *, site_url: str) -> str:
    """Compose the LinkedIn commentary text.

    Format:
        In the news today...

        • {headline 1}
        • {headline 2}
        • {headline 3}

        {site_url}

    The site URL goes on its own line at the end so the link unfurl is
    suppressed by the attached image card.
    """
    articles = ordered_picks(picks)
    if not articles:
        raise ValueError("compose_post called with no picks")

    bullets = "\n".join(f"• {a.headline.strip()}" for a in articles)
    text = f"In the news today...\n\n{bullets}\n\n{site_url}"

    if len(text) > LINKEDIN_MAX_COMMENTARY:
        text = text[: LINKEDIN_MAX_COMMENTARY - 1] + "…"
    return text


def article_ids(picks: Iterable[Article]) -> list[int]:
    return [a.id for a in picks]
