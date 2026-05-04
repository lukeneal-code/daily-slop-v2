from app.utils.slug import base_slug, disambiguate


def test_base_slug_strips_punctuation_and_lowercases() -> None:
    assert base_slug("IRAN HITS CARRIER; CARRIER UNAVAILABLE FOR COMMENT") == (
        "iran-hits-carrier-carrier-unavailable-for-comment"
    )


def test_base_slug_handles_unicode_and_apostrophes() -> None:
    assert base_slug("Charles Addams' Lament — A Café Story") == (
        "charles-addams-lament-a-cafe-story"
    )


def test_base_slug_truncates_to_max_length() -> None:
    long = "word " * 50
    slug = base_slug(long, max_length=40)
    assert len(slug) <= 40
    assert "-" in slug


def test_disambiguate_returns_input_when_unique() -> None:
    taken: set[str] = set()
    assert disambiguate("free-slot", exists=taken.__contains__) == "free-slot"


def test_disambiguate_appends_suffix_on_collision() -> None:
    taken = {"freddie-starr-ate-my-hamster"}
    out = disambiguate(
        "freddie-starr-ate-my-hamster", exists=taken.__contains__
    )
    assert out == "freddie-starr-ate-my-hamster-2"


def test_disambiguate_walks_until_open() -> None:
    taken = {"slug", "slug-2", "slug-3"}
    out = disambiguate("slug", exists=taken.__contains__)
    assert out == "slug-4"
