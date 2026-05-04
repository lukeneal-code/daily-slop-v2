import { api } from '../api/client';
import type { FrontPageResponse } from '../types';
import { useApi } from './useApi';

export function useFrontPage(date?: string) {
  return useApi<FrontPageResponse>(() => api.frontPage(date), [date ?? '__today__']);
}
