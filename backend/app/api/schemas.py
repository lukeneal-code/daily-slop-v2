from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str | None = None


class SourceRefOut(BaseModel):
    outlet: str
    url: str


class ArticleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    publish_date: date
    section: str
    writer: str
    headline: str
    subheadline: str
    image_url: str | None = None
    image_alt: str | None = None


class ArticleFull(ArticleSummary):
    body_html: str
    source: SourceRefOut | None = None


class FrontPageStoryOut(ArticleSummary):
    slot: str
    body_html: str


class FrontPageOut(BaseModel):
    publish_date: date
    stories: list[FrontPageStoryOut]


class SectionPageOut(BaseModel):
    section: SectionOut
    publish_date: date
    articles: list[ArticleSummary]
