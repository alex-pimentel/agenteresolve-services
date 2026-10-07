import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { CatalogPage } from './CatalogPage';

function renderPage() {
  return render(
    <MemoryRouter>
      <CatalogPage />
    </MemoryRouter>,
  );
}

describe('CatalogPage', () => {
  it('renders the heading and all 17 tool cards', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Ferramentas de IA' })).toBeInTheDocument();
    expect(screen.getAllByTestId('tool-card')).toHaveLength(17);
  });

  it('groups tools under the four category headings', () => {
    renderPage();
    for (const title of ['No navegador', 'Texto e LLM', 'Visão', 'Áudio']) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    }
  });

  it('links each card to its tool route', () => {
    renderPage();
    expect(screen.getByRole('link', { name: /translator/i })).toHaveAttribute('href', '/translate');
    expect(screen.getByRole('link', { name: /youtube2mp3/i })).toHaveAttribute(
      'href',
      '/youtube2mp3',
    );
    expect(screen.getByRole('link', { name: /louder/i })).toHaveAttribute('href', '/louder');
  });

  it('renders no beta badges now that every gateway tool is implemented', () => {
    renderPage();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(screen.getAllByText('No navegador').length).toBeGreaterThan(0);
  });
});
