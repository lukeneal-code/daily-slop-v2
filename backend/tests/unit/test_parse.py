import pytest

from app.llm.parse import parse_draft, parse_verdict


def test_parse_draft_handles_raw_json() -> None:
    raw = (
        '{"headline":"H","subheadline":"S","body":"<p>b</p>",'
        '"imageDescription":"img"}'
    )
    d = parse_draft(raw)
    assert d["headline"] == "H"
    assert d["body_html"] == "<p>b</p>"
    assert d["image_description"] == "img"


def test_parse_draft_strips_code_fences() -> None:
    raw = (
        "```json\n"
        '{"headline":"H","subheadline":"S","body":"<p>b</p>","imageDescription":"img"}\n'
        "```"
    )
    d = parse_draft(raw)
    assert d["headline"] == "H"


def test_parse_draft_accepts_snake_case_image_description() -> None:
    raw = (
        '{"headline":"H","subheadline":"S","body":"b",'
        '"image_description":"snake"}'
    )
    d = parse_draft(raw)
    assert d["image_description"] == "snake"


def test_parse_verdict_normalises_severity_and_score() -> None:
    raw = '{"decision":"revise","severity":"HIGH","score":3.2,"notes":"too AI-slop"}'
    v = parse_verdict(raw)
    assert v["decision"] == "revise"
    assert v["severity"] == "high"
    assert v["score"] == 3.2


def test_parse_verdict_rejects_bad_decision() -> None:
    raw = '{"decision":"sometimes","severity":"low","score":7,"notes":""}'
    with pytest.raises(ValueError):
        parse_verdict(raw)


def test_parse_verdict_defaults_severity_when_missing() -> None:
    v = parse_verdict('{"decision":"approve","score":8.1,"notes":"lovely"}')
    assert v["severity"] == "low"
