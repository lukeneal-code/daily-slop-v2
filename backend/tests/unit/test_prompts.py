from app.agents.prompts.loader import render, required_vars
from app.images.prompts import STYLE_PREFIX, build_prompt

BANNED_TOKENS = ["gothic", "macabre", "darkly", "horror", "speech bubble"]


def test_image_prefix_excludes_banned_tokens_in_positive_directives() -> None:
    # v1's gothic-Addams vocabulary must never appear at all in v2's prefix.
    lower = STYLE_PREFIX.lower()
    for token in ["macabre", "darkly", "addams family"]:
        assert token not in lower, f"v1 gothic token leaked: {token}"
    # The negation phrase should still be present so the model knows to avoid them.
    assert "no gothic" in lower
    assert "no text" in lower
    # `speech bubble` and `horror` are also forbidden — but only via the negation
    # clause (`no ... speech bubbles`, `no gothic or horror motifs`).
    for negated in ["speech bubble", "horror"]:
        idx = lower.find(negated)
        assert idx >= 0
        # The sentence containing the token must start with "no " (case-insensitive).
        sentence_start = max(lower.rfind(".", 0, idx), lower.rfind("!", 0, idx)) + 1
        sentence = lower[sentence_start:idx].lstrip()
        assert sentence.startswith("no "), (
            f"{negated!r} appears in a sentence without a leading negation: {sentence!r}"
        )


def test_build_prompt_combines_prefix_with_description() -> None:
    out = build_prompt("A figure shrugging at a podium")
    assert out.startswith(STYLE_PREFIX)
    assert "A figure shrugging at a podium" in out


def test_nigel_prompt_includes_section_token() -> None:
    rendered = render(
        "nigel.md",
        section="politics",
        length="LEAD",
        outlet="BBC",
        title="t",
        description="d",
        body_block="",
    )
    assert "politics" in rendered.lower()
    assert "FREDDIE STARR" in rendered  # canonical example preserved
    assert "JSON" in rendered


def test_nigel_prompt_drops_v1_gothic_tokens() -> None:
    rendered = render(
        "nigel.md",
        section="politics",
        length="LEAD",
        outlet="BBC",
        title="t",
        description="d",
        body_block="",
    )
    lower = rendered.lower()
    for token in ["macabre", "darkly humorous", "addams family"]:
        assert token not in lower


def test_steve_prompt_imposes_one_wild_claim() -> None:
    rendered = render(
        "steve.md",
        section="tech",
        length="SECTION",
        outlet="BBC",
        title="t",
        description="",
        body_block="",
    )
    assert "one wild claim" in rendered.lower()


def test_elle_review_required_variables() -> None:
    expected = {
        "outlet",
        "title",
        "description",
        "writer",
        "section",
        "draft_headline",
        "draft_subheadline",
        "draft_body_html",
        "steve_extra_strictness",
    }
    assert required_vars("elle_review.md") == expected


def test_elle_pushback_includes_writer_argument_var() -> None:
    assert "pushback" in required_vars("elle_pushback.md")
