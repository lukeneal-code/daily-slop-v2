import { Link } from 'react-router-dom';

import type { Article } from '../types';

interface SmallStoryProps {
  story: Article;
}

export default function SmallStory({ story }: SmallStoryProps) {
  return (
    <article className="small-story">
      <Link to={`/article/${story.slug}`}>
        <div className="small-story-image-wrapper">
          <img className="small-story-image" src={story.image_url} alt={story.image_alt} />
        </div>
      </Link>
      <Link to={`/article/${story.slug}`}>
        <h3 className="small-story-title">{story.headline}</h3>
      </Link>
      <p className="small-story-subtitle">{story.subheadline}</p>
    </article>
  );
}
