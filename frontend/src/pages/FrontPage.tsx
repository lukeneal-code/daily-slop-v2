import { useParams } from 'react-router-dom';

import AdSlot from '../components/AdSlot';
import HeadlineStory from '../components/HeadlineStory';
import SmallStory from '../components/SmallStory';
import { schemaFor } from '../ads/slots';
import { useFrontPage } from '../hooks/useFrontPage';

export default function FrontPage() {
  const { date } = useParams();
  const { data, loading, error } = useFrontPage(date);
  const slots = schemaFor('front_page', date ?? 'today');
  const displayDate = data?.publish_date ?? date ?? new Date().toISOString().slice(0, 10);

  if (loading) {
    return (
      <div className="loading">
        <p>Setting the type. One moment.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error">
        <p>Couldn&rsquo;t load today&rsquo;s edition: {error}</p>
      </div>
    );
  }

  const stories = data?.stories ?? [];
  const headline = stories.find((s) => s.slot === 'headline');
  const smalls = stories.filter((s) => s.slot !== 'headline');

  if (!headline) {
    return (
      <div className="no-stories">
        <h2>The presses didn&rsquo;t roll today</h2>
        <p>Check back at 6am London time. Or sooner, if our agents are feeling brisk.</p>
      </div>
    );
  }

  return (
    <>
      <AdSlot slot={slots[0]} date={displayDate} />
      <hr className="section-rule" />
      <HeadlineStory story={{ ...headline, body_html: '', source: undefined }} />
      <hr className="section-rule" />
      <AdSlot slot={slots[1]} date={displayDate} />
      <hr className="section-rule" />
      <div className="small-stories">
        {smalls.map((s) => (
          <SmallStory
            key={s.slug}
            story={{ ...s, body_html: '', source: undefined }}
          />
        ))}
      </div>
      <hr className="section-rule" />
      <AdSlot slot={slots[2]} date={displayDate} />
    </>
  );
}
