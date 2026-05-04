import type {
  Article,
  FrontPageResponse,
  Section,
  SectionPageResponse,
} from '../types';

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: 'omit' });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  sections: () => request<Section[]>('/api/sections'),
  frontPage: (date?: string) =>
    request<FrontPageResponse>(`/api/articles${date ? `?date=${date}` : ''}`),
  section: (slug: string, date?: string) =>
    request<SectionPageResponse>(
      `/api/articles?section=${slug}${date ? `&date=${date}` : ''}`,
    ),
  article: (slug: string) => request<Article>(`/api/articles/${slug}`),
  dates: () => request<string[]>('/api/dates'),
};
