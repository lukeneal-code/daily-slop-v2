"""Tiny templating layer for agent prompts.

We don't pull in Jinja2 just for `{{var}}` substitution — a regex pass is
sufficient and easier to audit. Loaders cache the file contents at import time.
"""

from __future__ import annotations

import re
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent
_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _load(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


_TEMPLATES: dict[str, str] = {}


def render(name: str, **vars: str) -> str:
    if name not in _TEMPLATES:
        _TEMPLATES[name] = _load(name)
    template = _TEMPLATES[name]

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in vars:
            raise KeyError(f"prompt {name} expects variable {{{{{key}}}}}")
        return vars[key]

    return _VAR_RE.sub(_sub, template)


def required_vars(name: str) -> set[str]:
    if name not in _TEMPLATES:
        _TEMPLATES[name] = _load(name)
    return set(_VAR_RE.findall(_TEMPLATES[name]))
