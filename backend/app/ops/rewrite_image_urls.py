"""One-shot: rewrite image_assets.public_url from `OLD_PREFIX` → `NEW_PREFIX`.

Reads the prefixes from env vars so this script can be reused for future swaps
(e.g. flipping back to `https://dailyslop.co.uk/images/` post-DNS-cutover).
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def main() -> int:
    old_prefix = os.environ.get(
        "OLD_PREFIX", "https://dailyslop.co.uk/images/"
    )
    new_prefix = os.environ.get(
        "NEW_PREFIX",
        "https://storage.googleapis.com/daily-slop-v2-images-prod/",
    )
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    if not url:
        print("[rewrite] DATABASE_URL_SYNC required", file=sys.stderr)
        return 2

    print(f"[rewrite] {old_prefix!r} -> {new_prefix!r}")
    engine = create_engine(url)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE image_assets "
                "SET public_url = :new_prefix || SUBSTR(public_url, LENGTH(:old_prefix) + 1) "
                "WHERE public_url LIKE :pattern"
            ),
            {
                "old_prefix": old_prefix,
                "new_prefix": new_prefix,
                "pattern": old_prefix + "%",
            },
        )
        print(f"[rewrite] rowcount={result.rowcount}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
