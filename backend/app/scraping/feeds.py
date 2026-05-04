"""RSS feed registry, per-section.

Each section has 1-2 feeds; v2 leans on the same outlets v1 used (BBC, Guardian,
Sky, Indy, Mirror) but routes them by topic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feed:
    outlet: str
    url: str
    section: str


FEEDS: tuple[Feed, ...] = (
    Feed("BBC", "https://feeds.bbci.co.uk/news/politics/rss.xml", "politics"),
    Feed("Guardian", "https://www.theguardian.com/politics/rss", "politics"),
    Feed("BBC", "https://feeds.bbci.co.uk/news/business/rss.xml", "business"),
    Feed("Guardian", "https://www.theguardian.com/business/rss", "business"),
    Feed("BBC", "https://feeds.bbci.co.uk/news/technology/rss.xml", "tech"),
    Feed("Guardian", "https://www.theguardian.com/technology/rss", "tech"),
    Feed("Guardian", "https://www.theguardian.com/culture/rss", "culture"),
    Feed("BBC", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "culture"),
    Feed("BBC", "https://feeds.bbci.co.uk/sport/rss.xml", "sport"),
    Feed("Guardian", "https://www.theguardian.com/sport/rss", "sport"),
    Feed("BBC", "https://feeds.bbci.co.uk/news/uk/royal_family/rss.xml", "royals"),
)


def feeds_for_section(section: str) -> tuple[Feed, ...]:
    return tuple(f for f in FEEDS if f.section == section)
