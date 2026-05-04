"""RSS scraping: pulls each feed, normalises items, dedupes by external_id."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import feedparser

from app.scraping.feeds import FEEDS, Feed, feeds_for_section

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceItem:
    external_id: str
    outlet: str
    title: str
    description: str
    url: str
    image_url: str | None
    published_at: datetime | None
    section: str


def _external_id(outlet: str, link: str, guid: str | None) -> str:
    raw = guid or link
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{outlet.lower()}:{digest}"


def _published(entry: dict[str, Any]) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        y, m, d, h, mi, s = parsed[:6]
        return datetime(y, m, d, h, mi, s, tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _image(entry: dict[str, Any]) -> str | None:
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media:
        url = media[0].get("url")
        if isinstance(url, str):
            return url
    enclosures = entry.get("enclosures") or []
    for e in enclosures:
        if isinstance(e, dict) and e.get("type", "").startswith("image"):
            href = e.get("href") or e.get("url")
            if isinstance(href, str):
                return href
    return None


def _items_from_feed(feed: Feed, parsed: feedparser.FeedParserDict) -> list[SourceItem]:
    items: list[SourceItem] = []
    for entry in parsed.entries:
        link = entry.get("link") or ""
        guid = entry.get("id") or entry.get("guid")
        if not link:
            continue
        items.append(
            SourceItem(
                external_id=_external_id(feed.outlet, link, guid),
                outlet=feed.outlet,
                title=(entry.get("title") or "").strip(),
                description=(entry.get("summary") or "").strip(),
                url=link,
                image_url=_image(entry),
                published_at=_published(entry),
                section=feed.section,
            )
        )
    return items


def scrape_feed(feed: Feed, *, parser: Any = feedparser.parse) -> list[SourceItem]:
    """Pull a single feed. Wrapped so tests can pass a stub parser."""
    parsed = parser(feed.url)
    if parsed.bozo:
        log.warning("feed %s flagged bozo: %s", feed.url, parsed.get("bozo_exception"))
    return _items_from_feed(feed, parsed)


def scrape_all(*, parser: Any = feedparser.parse) -> list[SourceItem]:
    items: list[SourceItem] = []
    for feed in FEEDS:
        items.extend(scrape_feed(feed, parser=parser))
    return items


def scrape_section(section: str, *, parser: Any = feedparser.parse) -> list[SourceItem]:
    items: list[SourceItem] = []
    for feed in feeds_for_section(section):
        items.extend(scrape_feed(feed, parser=parser))
    return items
