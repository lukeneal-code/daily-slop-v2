from datetime import UTC, datetime
from typing import Any

from app.scraping.feeds import Feed
from app.scraping.rss import scrape_feed


class _FakeParsed:
    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self.entries = entries
        self.bozo = False
        self._extra: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._extra.get(key, default)


def _make_parser(entries: list[dict[str, Any]]):
    def _parse(_url: str) -> _FakeParsed:
        return _FakeParsed(entries)

    return _parse


def test_scrape_feed_normalises_entries() -> None:
    feed = Feed(outlet="BBC", url="https://example.com/rss", section="politics")
    parser = _make_parser(
        [
            {
                "id": "guid-1",
                "link": "https://bbc.co.uk/article-1",
                "title": "Chancellor announces fuel duty rise",
                "summary": "Detail.",
                "published_parsed": (2026, 5, 2, 10, 0, 0, 0, 0, 0),
            },
            {
                "id": "guid-2",
                "link": "https://bbc.co.uk/article-2",
                "title": "By-election upset",
                "summary": "More detail.",
                "media_thumbnail": [{"url": "https://bbc.co.uk/img.jpg"}],
            },
        ]
    )

    items = scrape_feed(feed, parser=parser)

    assert len(items) == 2
    assert items[0].section == "politics"
    assert items[0].outlet == "BBC"
    assert items[0].external_id.startswith("bbc:")
    assert items[0].published_at == datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
    assert items[1].image_url == "https://bbc.co.uk/img.jpg"


def test_scrape_feed_skips_entries_without_link() -> None:
    feed = Feed(outlet="BBC", url="https://example.com/rss", section="tech")
    parser = _make_parser([{"title": "no link", "id": "x"}, {"link": "https://x", "title": "ok"}])

    items = scrape_feed(feed, parser=parser)

    assert len(items) == 1
    assert items[0].title == "ok"


def test_external_id_is_stable_for_same_link() -> None:
    feed = Feed(outlet="Guardian", url="https://example.com/rss", section="business")
    parser = _make_parser([{"link": "https://g/article", "title": "t", "id": "guid"}])

    a = scrape_feed(feed, parser=parser)[0]
    b = scrape_feed(feed, parser=parser)[0]

    assert a.external_id == b.external_id
