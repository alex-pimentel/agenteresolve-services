import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { TOOLS } from '../data/tools';
import { CatalogPage } from './CatalogPage';

function renderPage() {
  return render(
    <MemoryRouter>
      <CatalogPage />
    </MemoryRouter>,
  );
}

describe('CatalogPage', () => {
  it('renders the heading and one card per tool in the catalogue', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: 'Ferramentas de IA' })).toBeInTheDocument();
    // Quantas ferramentas existem é do canônico do gateway (e o contrato em
    // packages/common/tests/test_spa_catalog_contract.py cuida da igualdade); aqui o que importa é
    // que a página renderiza o catálogo inteiro, sem sobra nem falta.
    expect(screen.getAllByTestId('tool-card')).toHaveLength(TOOLS.length);
    expect(screen.getByRole('link', { name: new RegExp(TOOLS[0].name, 'i') })).toBeInTheDocument();
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
    expect(screen.getByRole('link', { name: /louder/i })).toHaveAttribute('href', '/louder');
    expect(screen.getByRole('link', { name: /gerador de qr codes/i })).toHaveAttribute(
      'href',
      '/qrcode',
    );
    expect(screen.getByRole('link', { name: /imposition/i })).toHaveAttribute(
      'href',
      '/imposition',
    );
  });

  it('does not advertise a beta bucket now that every listed tool is implemented', () => {
    renderPage();
    const implemented = TOOLS.filter((tool) => tool.implemented).length;
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
    expect(
      screen.getByText(`${TOOLS.length} ferramentas · ${implemented} disponíveis agora.`),
    ).toBeInTheDocument();
    expect(screen.getAllByText('No navegador').length).toBeGreaterThan(0);
  });
});
