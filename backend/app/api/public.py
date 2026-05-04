from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ArticleFull,
    ArticleSummary,
    FrontPageOut,
    FrontPageStoryOut,
    SectionOut,
    SectionPageOut,
    SourceRefOut,
)
from app.db import repo
from app.db.models import Article, ImageAsset
from app.db.session import get_session

router = APIRouter(tags=["public"])


def _image_url(asset: ImageAsset | None, fallback: str | None = None) -> str | None:
    if asset is None:
        return fallback
    return asset.public_url


def _summary(a: Article) -> ArticleSummary:
    return ArticleSummary(
        slug=a.slug,
        publish_date=a.publish_date,
        section=a.section,
        writer=a.writer,
        headline=a.headline,
        subheadline=a.subheadline,
        image_url=_image_url(a.image_asset),
        image_alt=a.image_alt,
    )


@router.get("/sections", response_model=list[SectionOut])
async def list_sections(session: AsyncSession = Depends(get_session)) -> list[SectionOut]:
    sections = await repo.list_sections(session)
    return [SectionOut.model_validate(s) for s in sections]


@router.get("/dates", response_model=list[date])
async def list_dates(session: AsyncSession = Depends(get_session)) -> list[date]:
    return await repo.published_dates(session)


@router.get("/articles")
async def list_articles(
    session: AsyncSession = Depends(get_session),
    on_date: date | None = Query(default=None, alias="date"),
    section: str | None = None,
) -> FrontPageOut | SectionPageOut:
    target = on_date or await repo.latest_publish_date(session) or date.today()

    if section is None:
        stories = await repo.front_page(session, on_date=target)
        return FrontPageOut(
            publish_date=target,
            stories=[
                FrontPageStoryOut(
                    slot=getattr(a, "slot", "headline"),
                    body_html=a.body_html,
                    **_summary(a).model_dump(),
                )
                for a in stories
            ],
        )

    sections = {s.slug: s for s in await repo.list_sections(session)}
    if section not in sections:
        raise HTTPException(status_code=404, detail=f"unknown section: {section}")
    articles = await repo.section_articles(session, section=section, on_date=target)
    return SectionPageOut(
        section=SectionOut.model_validate(sections[section]),
        publish_date=target,
        articles=[_summary(a) for a in articles],
    )


@router.get("/articles/{slug}", response_model=ArticleFull)
async def get_article(
    slug: str, session: AsyncSession = Depends(get_session)
) -> ArticleFull:
    article = await repo.article_by_slug(session, slug=slug)
    if article is None:
        raise HTTPException(status_code=404, detail=f"unknown article: {slug}")
    source = None
    if article.source is not None:
        source = SourceRefOut(outlet=article.source.outlet, url=article.source.url)
    return ArticleFull(
        **_summary(article).model_dump(),
        body_html=article.body_html,
        source=source,
    )
