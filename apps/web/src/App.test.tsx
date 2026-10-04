import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { App } from './App';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe('App routing', () => {
  it('renders the catalogue at /', () => {
    renderAt('/');
    expect(screen.getByRole('heading', { name: 'Ferramentas de IA' })).toBeInTheDocument();
  });

  it('renders a tool page at /:slug', () => {
    renderAt('/translate');
    expect(screen.getByRole('heading', { name: 'Translator' })).toBeInTheDocument();
  });

  it('renders the not-found page for unknown routes', () => {
    renderAt('/a/b/c');
    expect(screen.getByRole('heading', { name: 'Ferramenta não encontrada' })).toBeInTheDocument();
  });
});
