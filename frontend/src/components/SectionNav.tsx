import { NavLink } from 'react-router-dom';

import type { SectionSlug } from '../types';

const SECTIONS: { slug: SectionSlug; name: string }[] = [
  { slug: 'politics', name: 'Politics' },
  { slug: 'business', name: 'Business' },
  { slug: 'tech', name: 'Tech' },
  { slug: 'culture', name: 'Culture' },
  { slug: 'sport', name: 'Sport' },
  { slug: 'royals', name: 'Royals' },
];

export default function SectionNav() {
  return (
    <nav className="section-nav" aria-label="Sections">
      <ul className="section-nav-list">
        <li className="section-nav-item">
          <NavLink to="/" end className="section-nav-link">
            Front Page
          </NavLink>
        </li>
        {SECTIONS.map((s) => (
          <li key={s.slug} className="section-nav-item">
            <span className="section-nav-divider" aria-hidden>
              &middot;
            </span>
            <NavLink to={`/section/${s.slug}`} className="section-nav-link">
              {s.name}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
