from app.scraping.feeds import FEEDS, feeds_for_section


def test_every_section_has_at_least_one_feed() -> None:
    expected = {"politics", "business", "tech", "culture", "sport", "royals"}
    have = {f.section for f in FEEDS}
    assert expected.issubset(have)


def test_feeds_for_section_filters_correctly() -> None:
    politics = feeds_for_section("politics")
    assert all(f.section == "politics" for f in politics)
    assert {f.outlet for f in politics} == {"BBC", "Guardian"}


def test_royals_only_uses_bbc_feed_for_now() -> None:
    royals = feeds_for_section("royals")
    assert {f.outlet for f in royals} == {"BBC"}
