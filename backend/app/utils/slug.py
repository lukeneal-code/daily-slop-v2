"""URL slug generation. Slugs are unique within (publish_date, section).

Collision strategy: append `-2`, `-3`, ... until unique. The caller is responsible
for the uniqueness check against the DB; this module only handles the string transform.
"""

from __future__ import annotations

from collections.abc import Callable

from slugify import slugify as _slugify  # python-slugify


def base_slug(text: str, *, max_length: int = 80) -> str:
    return _slugify(text, max_length=max_length, lowercase=True, separator="-")


def disambiguate(
    candidate: str, *, exists: Callable[[str], bool], max_attempts: int = 50
) -> str:
    if not exists(candidate):
        return candidate
    for n in range(2, max_attempts + 2):
        attempt = f"{candidate}-{n}"
        if not exists(attempt):
            return attempt
    raise RuntimeError(f"could not disambiguate slug after {max_attempts} attempts: {candidate}")
