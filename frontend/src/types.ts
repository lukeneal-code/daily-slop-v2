export type SectionSlug =
  | 'politics'
  | 'business'
  | 'tech'
  | 'culture'
  | 'sport'
  | 'royals';

export interface Section {
  slug: SectionSlug;
  name: string;
  description?: string;
}

export type FrontPageSlot = 'headline' | 'small_1' | 'small_2';

export interface Article {
  slug: string;
  publish_date: string;
  section: SectionSlug;
  writer: 'nigel' | 'steve';
  headline: string;
  subheadline: string;
  body_html: string;
  image_url: string;
  image_alt: string;
  source?: { outlet: string; url: string };
}

export interface FrontPageStory extends Article {
  slot: FrontPageSlot;
}

export interface FrontPageResponse {
  publish_date: string;
  stories: FrontPageStory[];
}

export interface SectionPageResponse {
  section: Section;
  publish_date: string;
  articles: Article[];
}
