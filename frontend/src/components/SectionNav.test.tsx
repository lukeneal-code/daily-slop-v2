import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import SectionNav from './SectionNav';

function withRouter(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <SectionNav />
    </MemoryRouter>,
  );
}

describe('<SectionNav />', () => {
  it('renders all six sections plus front page', () => {
    withRouter('/');
    expect(screen.getByText('Front Page')).toBeInTheDocument();
    for (const name of ['Politics', 'Business', 'Tech', 'Culture', 'Sport', 'Royals']) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
  });

  it('marks the active section with aria-current', () => {
    withRouter('/section/politics');
    const link = screen.getByRole('link', { name: 'Politics' });
    expect(link).toHaveAttribute('aria-current', 'page');
  });
});
