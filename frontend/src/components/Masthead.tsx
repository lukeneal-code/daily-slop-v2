interface MastheadProps {
  date?: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T12:00:00');
  return date.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

function todayLondon(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/London' });
}

export default function Masthead({ date }: MastheadProps) {
  const display = date ?? todayLondon();
  return (
    <header className="masthead">
      <div className="masthead-top-bar">
        <span className="masthead-est">Est. 2026</span>
        <span className="masthead-price">Price: Free (worth every penny)</span>
      </div>
      <div className="masthead-title-row">
        <div className="masthead-ornament">&#9733;</div>
        <h1 className="masthead-title">The Daily Slop</h1>
        <div className="masthead-ornament">&#9733;</div>
      </div>
      <p className="masthead-tagline">&ldquo;All the news that&rsquo;s unfit to print&rdquo;</p>
      <p className="masthead-date">{formatDate(display)}</p>
    </header>
  );
}
