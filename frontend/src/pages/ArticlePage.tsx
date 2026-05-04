import { useParams } from 'react-router-dom';

import AdSlot from '../components/AdSlot';
import { schemaFor } from '../ads/slots';
import { useArticle } from '../hooks/useArticle';

export default function ArticlePage() {
  const { slug } = useParams();
  const { data, loading, error } = useArticle(slug ?? '');
  const slots = schemaFor('article_page', slug ?? 'unknown');
  const displayDate = data?.publish_date ?? new Date().toISOString().slice(0, 10);

  if (loading) {
    return (
      <div className="loading">
        <p>Pulling the page from the press.</p>
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="error">
        <p>{error ?? 'Article not found.'}</p>
      </div>
    );
  }

  // Split the body so we can drop an MPU after the second paragraph.
  const paragraphs = data.body_html.split(/(?<=<\/p>)/);
  const before = paragraphs.slice(0, 2).join('');
  const after = paragraphs.slice(2).join('');

  return (
    <article className="article-page">
      <p className="article-section-tag">{data.section}</p>
      {data.image_url ? (
        <div className="headline-image-wrapper">
          <img className="headline-image" src={data.image_url} alt={data.image_alt ?? ''} />
        </div>
      ) : null}
      <h2 className="headline-title">{data.headline}</h2>
      <p className="headline-subtitle">{data.subheadline}</p>

      <div className="headline-body">
        <div dangerouslySetInnerHTML={{ __html: before }} />
        <AdSlot slot={slots[0]} date={displayDate} />
        <div dangerouslySetInnerHTML={{ __html: after }} />
      </div>

      {data.source ? (
        <p className="story-source">
          inspired by <span className="source-outlet">{data.source.outlet}</span>
        </p>
      ) : null}

      <hr className="section-rule thin" />
      <AdSlot slot={slots[1]} date={displayDate} />
    </article>
  );
}
