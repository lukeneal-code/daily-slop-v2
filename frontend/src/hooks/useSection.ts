import { api } from '../api/client';
import type { SectionPageResponse } from '../types';
import { useApi } from './useApi';

export function useSection(slug: string, date?: string) {
  return useApi<SectionPageResponse>(
    () => api.section(slug, date),
    [slug, date ?? '__today__'],
  );
}
