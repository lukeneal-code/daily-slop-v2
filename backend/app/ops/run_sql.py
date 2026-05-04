"""Run an arbitrary SQL statement against the configured Postgres.

Reads the statement from `OPS_SQL` (preferred) or stdin. Used as a one-shot
Cloud Run job for migrations / data fixes that can't be expressed as Alembic
migrations (e.g. URL rewrites after env changes).

Usage:
    OPS_SQL="UPDATE foo SET x = 1 WHERE y = 2" python -m app.ops.run_sql
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text


def main() -> int:
    sql = os.environ.get("OPS_SQL") or sys.stdin.read()
    sql = sql.strip()
    if not sql:
        print("[run_sql] no SQL provided (OPS_SQL env or stdin)", file=sys.stderr)
        return 2

    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        print("[run_sql] DATABASE_URL_SYNC required", file=sys.stderr)
        return 2
    # Allow only sync drivers here.
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")

    engine = create_engine(url)
    with engine.begin() as conn:
        result = conn.execute(text(sql))
        print(f"[run_sql] rowcount={result.rowcount}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
