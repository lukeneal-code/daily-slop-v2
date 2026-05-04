export type AdSize = 'leaderboard' | 'mpu' | 'skyscraper' | 'native';

export type PageId = 'front_page' | 'section_page' | 'article_page';

export type AdPlacement =
  | 'below_masthead'
  | 'between_smalls'
  | 'below_fold_right'
  | 'below_section_nav'
  | 'after_card_2'
  | 'after_paragraph_2'
  | 'right_rail_desktop';

export interface AdSlotSchema {
  id: string;
  size: AdSize;
  placement: AdPlacement;
}

const FRONT_PAGE_SCHEMA: AdSlotSchema[] = [
  { id: 'fp-leader', size: 'leaderboard', placement: 'below_masthead' },
  { id: 'fp-native', size: 'native', placement: 'between_smalls' },
  { id: 'fp-mpu', size: 'mpu', placement: 'below_fold_right' },
];

const SECTION_PAGE_SCHEMA_A: AdSlotSchema[] = [
  { id: 'sec-leader', size: 'leaderboard', placement: 'below_section_nav' },
  { id: 'sec-mpu', size: 'mpu', placement: 'after_card_2' },
];

const SECTION_PAGE_SCHEMA_B: AdSlotSchema[] = [
  { id: 'sec-native', size: 'native', placement: 'below_section_nav' },
  { id: 'sec-leader', size: 'leaderboard', placement: 'after_card_2' },
];

const ARTICLE_PAGE_SCHEMA: AdSlotSchema[] = [
  { id: 'art-mpu', size: 'mpu', placement: 'after_paragraph_2' },
  { id: 'art-sky', size: 'skyscraper', placement: 'right_rail_desktop' },
];

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h;
}

export function schemaFor(page: PageId, key: string): AdSlotSchema[] {
  if (page === 'front_page') return FRONT_PAGE_SCHEMA;
  if (page === 'article_page') return ARTICLE_PAGE_SCHEMA;
  return hashStr(key) % 2 === 0 ? SECTION_PAGE_SCHEMA_A : SECTION_PAGE_SCHEMA_B;
}

export function pickCreativeIndex(
  totalCreatives: number,
  date: string,
  slotId: string,
): number {
  return hashStr(`${date}|${slotId}`) % totalCreatives;
}
