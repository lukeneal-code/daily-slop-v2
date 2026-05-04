"""LLM-as-judge prompts for the nightly eval suite."""

from __future__ import annotations

JUDGE_HUMOUR = """You are evaluating a satirical British newspaper article on behalf of *The Daily Slop*.

Score the article 1-10 on the following four axes, weighting equally:

1. **Deadpan**: does it state absurd things flatly, in a British register, without winking?
2. **Surprise**: is the angle one a reader wouldn't have predicted from the source?
3. **Originality**: are the gags fresh, or are they tired ("AI ate my homework", em-dash overuse, listicle structure)?
4. **British register**: does it sound like *Private Eye* / *The Daily Mash*, not generic LLM satire?

Give the average as a single 1-10 number with one decimal. Reject as 0 if the piece is offensive or punches down.

ARTICLE:
- Headline: "{{headline}}"
- Subheadline: "{{subheadline}}"
- Body (HTML): {{body_html}}
- Section: {{section}}
- Writer: {{writer}}

Respond with raw JSON only: {"score": 0.0, "reasoning": "one sentence"}.
"""

JUDGE_HUMAN_READABILITY = """You are evaluating whether a satirical British newspaper article reads as **written by a human** for *The Daily Slop*.

Score 1-10 weighting equally:

1. **Flow**: do paragraphs actually transition? Does the rhythm vary?
2. **Scan-ability**: can a reader skim and still come away amused?
3. **Headline punch**: does the headline land in 8 words or fewer? Tabloid energy?
4. **Could-pass-for-a-human**: would this fool a *Daily Mash* subeditor?

Penalise heavily for: three-adjective stacks, "in a world where" framing, em-dash overuse, repetitive sentence rhythms, listicle structure, vague abstractions.

ARTICLE:
- Headline: "{{headline}}"
- Subheadline: "{{subheadline}}"
- Body (HTML): {{body_html}}

Respond with raw JSON only: {"score": 0.0, "reasoning": "one sentence"}.
"""
