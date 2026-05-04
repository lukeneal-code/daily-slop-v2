import { Link } from 'react-router-dom';

import type { Article } from '../types';

interface ArticleCardProps {
  story: Article;
}

export default function ArticleCard({ story }: ArticleCardProps) {
  return (
    <article className="article-card">
      <Link to={`/article/${story.slug}`}>
        <img
          className="article-card-image"
          src={story.image_url}
          alt={story.image_alt}
          loading="lazy"
        />
      </Link>
      <div>
        <Link to={`/article/${story.slug}`}>
          <h3 className="article-card-title">{story.headline}</h3>
        </Link>
        <p className="article-card-subtitle">{story.subheadline}</p>
      </div>
    </article>
  );
}
