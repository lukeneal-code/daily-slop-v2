import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import Masthead from './Masthead';

describe('<Masthead />', () => {
  it('renders the title and ornaments (red stars either side)', () => {
    const { container } = render(<Masthead date="2026-05-02" />);
    expect(screen.getByText('The Daily Slop')).toBeInTheDocument();
    const ornaments = container.querySelectorAll('.masthead-ornament');
    expect(ornaments).toHaveLength(2);
    for (const o of ornaments) {
      expect(o.textContent).toBe('★');
    }
  });

  it('formats the masthead date in en-GB long form', () => {
    render(<Masthead date="2026-05-02" />);
    expect(screen.getByText(/Saturday, 2 May 2026/)).toBeInTheDocument();
  });
});
