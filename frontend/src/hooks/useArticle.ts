import { api } from '../api/client';
import type { Article } from '../types';
import { useApi } from './useApi';

export function useArticle(slug: string) {
  return useApi<Article>(() => api.article(slug), [slug]);
}
