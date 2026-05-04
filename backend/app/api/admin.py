from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel

from app.api.auth import verify_scheduler_or_dev_token
from app.config import get_settings
from app.pipeline.daily import run_daily
from app.social.runner import post_today_to_linkedin

log = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


class GenerateRequest(BaseModel):
    publish_date: date | None = None


class GenerateResponse(BaseModel):
    accepted: bool
    publish_date: date
    total_articles: int
    rejected_count: int


@router.post(
    "/generate", status_code=status.HTTP_200_OK, response_model=GenerateResponse
)
async def trigger_generate(
    body: GenerateRequest | None = None,
    _principal: Annotated[str, Depends(verify_scheduler_or_dev_token)] = "",
    authorization: Annotated[str | None, Header()] = None,
) -> GenerateResponse:
    """Run the daily pipeline synchronously and return when persistence is done.

    Cloud Run scales instances to zero shortly after the request returns, so we
    can't safely use FastAPI's `BackgroundTasks` here — the task would be killed
    mid-pipeline. The request keeps the instance alive until completion.
    Container request timeout is configured for 15 minutes which is plenty for
    18 articles + images.
    """
    settings = get_settings()
    target = (body and body.publish_date) or _today_london()
    log.info("admin/generate triggered date=%s", target)
    result = await run_daily(target, steve_quota=settings.steve_quota)
    return GenerateResponse(
        accepted=True,
        publish_date=result.publish_date,
        total_articles=result.total_articles,
        rejected_count=result.rejected_count,
    )


class PostLinkedInRequest(BaseModel):
    publish_date: date | None = None


class PostLinkedInResponse(BaseModel):
    publish_date: date
    status: str
    post_urn: str | None
    article_ids: list[int]


@router.post(
    "/post-linkedin",
    status_code=status.HTTP_200_OK,
    response_model=PostLinkedInResponse,
)
async def trigger_post_linkedin(
    body: PostLinkedInRequest | None = None,
    _principal: Annotated[str, Depends(verify_scheduler_or_dev_token)] = "",
) -> PostLinkedInResponse:
    target = (body and body.publish_date) or _today_london()
    log.info("admin/post-linkedin triggered date=%s", target)
    result = await post_today_to_linkedin(target)
    return PostLinkedInResponse(
        publish_date=result.publish_date,
        status=result.status,
        post_urn=result.post_urn,
        article_ids=result.article_ids,
    )


def _today_london() -> date:
    # Local-friendly default. Cloud Scheduler will pass an explicit date in body if needed.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Europe/London")).date()
