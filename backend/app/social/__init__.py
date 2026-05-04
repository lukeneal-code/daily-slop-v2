"""Outbound social posts (LinkedIn).

The runner is invoked once per day from `/admin/post-linkedin`, separate from
the article-generation pipeline so a LinkedIn outage can't poison a run.
"""
