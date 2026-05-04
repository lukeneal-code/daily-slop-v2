from app.agents.router import choose_writer
from app.agents.state import SourceRef


def _src(section: str = "politics", external_id: str = "bbc:abc123") -> SourceRef:
    return SourceRef(
        id=1,
        external_id=external_id,
        outlet="BBC",
        title="Title",
        description="Desc",
        body_text="",
        url="https://example.com/x",
        section=section,  # type: ignore[typeddict-item]
    )


def test_steve_never_routed_to_royals() -> None:
    for i in range(200):
        assert choose_writer(_src(section="royals", external_id=f"src:{i}")) == "nigel"


def test_steve_never_routed_to_headline_candidates() -> None:
    for i in range(200):
        s = _src(section="politics", external_id=f"src:{i}")
        assert choose_writer(s, is_headline_candidate=True) == "nigel"


def test_choice_is_deterministic_for_same_external_id() -> None:
    s = _src(section="tech", external_id="bbc:abc123")
    a = choose_writer(s)
    b = choose_writer(s)
    assert a == b


def test_quota_zero_always_returns_nigel() -> None:
    for i in range(50):
        assert choose_writer(_src(external_id=f"src:{i}"), steve_quota=0.0) == "nigel"


def test_quota_one_always_returns_steve_outside_royals_and_headlines() -> None:
    for i in range(50):
        assert (
            choose_writer(_src(section="tech", external_id=f"src:{i}"), steve_quota=1.0)
            == "steve"
        )


def test_steve_share_approximately_matches_quota() -> None:
    quota = 0.25
    sample = [
        choose_writer(_src(section="tech", external_id=f"src:{i}"), steve_quota=quota)
        for i in range(800)
    ]
    steve_share = sum(1 for w in sample if w == "steve") / len(sample)
    assert abs(steve_share - quota) < 0.05  # within 5 percentage points
