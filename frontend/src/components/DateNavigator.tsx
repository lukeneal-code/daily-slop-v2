import { useNavigate } from 'react-router-dom';

interface DateNavigatorProps {
  current: string;
  available: string[];
}

function fmt(date: string): string {
  return new Date(date + 'T12:00:00').toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
  });
}

export default function DateNavigator({ current, available }: DateNavigatorProps) {
  const navigate = useNavigate();
  const sorted = [...available].sort();
  const idx = sorted.indexOf(current);
  const prev = idx > 0 ? sorted[idx - 1] : null;
  const next = idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null;

  return (
    <nav className="date-navigator" aria-label="Past editions">
      <button
        type="button"
        className="nav-button"
        disabled={!prev}
        onClick={() => prev && navigate(`/date/${prev}`)}
      >
        &larr; Older
      </button>
      <span className="nav-divider" aria-hidden>
        |
      </span>
      <button
        type="button"
        className="nav-button"
        disabled={!next}
        onClick={() => navigate(next ? `/date/${next}` : '/')}
      >
        {next ? `Newer (${fmt(next)})` : 'Today'} &rarr;
      </button>
    </nav>
  );
}
