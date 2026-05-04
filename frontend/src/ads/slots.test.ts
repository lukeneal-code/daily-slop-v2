import { describe, expect, it } from 'vitest';

import { pickCreativeIndex, schemaFor } from './slots';

describe('schemaFor', () => {
  it('returns the front-page schema with three slots', () => {
    const slots = schemaFor('front_page', 'whatever');
    expect(slots).toHaveLength(3);
    expect(slots[0].size).toBe('leaderboard');
  });

  it('returns the article-page schema with mpu + skyscraper', () => {
    const slots = schemaFor('article_page', 'irrelevant');
    expect(slots.map((s) => s.size)).toEqual(['mpu', 'skyscraper']);
  });

  it('rotates section schemas deterministically per section slug', () => {
    expect(schemaFor('section_page', 'politics')).toEqual(
      schemaFor('section_page', 'politics'),
    );
    expect(schemaFor('section_page', 'tech')).toEqual(
      schemaFor('section_page', 'tech'),
    );
  });
});

describe('pickCreativeIndex', () => {
  it('is stable for the same (date, slot) pair', () => {
    const a = pickCreativeIndex(10, '2026-05-02', 'fp-mpu');
    const b = pickCreativeIndex(10, '2026-05-02', 'fp-mpu');
    expect(a).toBe(b);
  });

  it('differs across days for the same slot', () => {
    const a = pickCreativeIndex(10, '2026-05-02', 'fp-mpu');
    const b = pickCreativeIndex(10, '2026-05-03', 'fp-mpu');
    expect(a).not.toBe(b);
  });

  it('returns indices in [0, total)', () => {
    for (let i = 0; i < 50; i++) {
      const idx = pickCreativeIndex(10, `2026-05-${String((i % 28) + 1).padStart(2, '0')}`, `slot-${i}`);
      expect(idx).toBeGreaterThanOrEqual(0);
      expect(idx).toBeLessThan(10);
    }
  });
});
