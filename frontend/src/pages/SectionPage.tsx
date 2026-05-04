import { Fragment } from 'react';
import { useParams } from 'react-router-dom';

import AdSlot from '../components/AdSlot';
import ArticleCard from '../components/ArticleCard';
import { schemaFor } from '../ads/slots';
import { useSection } from '../hooks/useSection';

const SECTION_BLURBS: Record<string, string> = {
  politics: 'Westminster, elections, party drama — but funnier.',
  business: 'Markets, CEOs, and the slow violence of a quarterly earnings call.',
  tech: 'AI hype, Silicon Valley, and one too many seed rounds.',
  culture: 'Arts, media, celebrity, and the slow death of the dinner party.',
  sport: 'Football, Olympics, and dignified middle-aged men weeping at racquets.',
  royals: 'Palace gossip, ceremony, and ribbon-cutting in industrial quantities.',
};

export default function SectionPage() {
  const { slug = 'politics' } = useParams();
  const { data, loading, error } = useSection(slug);
  const slots = schemaFor('section_page', slug);
  const displayDate = data?.publish_date ?? new Date().toISOString().slice(0, 10);

  return (
    <>
      <header className="section-page-header">
        <h2 className="section-page-title">{data?.section.name ?? slug}</h2>
        <p className="section-page-blurb">
          {data?.section.description ?? SECTION_BLURBS[slug]}
        </p>
      </header>

      <AdSlot slot={slots[0]} date={displayDate} />
      <hr className="section-rule thin" />

      {loading ? (
        <div className="loading">
          <p>Filing copy. Stand by.</p>
        </div>
      ) : error ? (
        <div className="error">
          <p>Couldn&rsquo;t load this section: {error}</p>
        </div>
      ) : !data || data.articles.length === 0 ? (
        <div className="no-stories">
          <p>No articles in this section yet today.</p>
        </div>
      ) : (
        data.articles.map((a, i) => (
          <Fragment key={a.slug}>
            <ArticleCard story={{ ...a, body_html: '' }} />
            {i === 1 ? <AdSlot slot={slots[1]} date={displayDate} /> : null}
          </Fragment>
        ))
      )}
    </>
  );
}
