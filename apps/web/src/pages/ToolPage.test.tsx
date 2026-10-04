import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import { ToolPage } from './ToolPage';

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>();
  return {
    ...actual,
    createTextJob: vi.fn(),
    createFileJob: vi.fn(),
    pollJob: vi.fn(),
    fetchText: vi.fn(),
  };
});

import * as api from '../lib/api';

const createTextJobMock = vi.mocked(api.createTextJob);
const createFileJobMock = vi.mocked(api.createFileJob);
const pollJobMock = vi.mocked(api.pollJob);
const fetchTextMock = vi.mocked(api.fetchText);

function renderSlug(slug: string) {
  return render(
    <MemoryRouter initialEntries={[`/${slug}`]}>
      <Routes>
        <Route path="/:slug" element={<ToolPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function doneJob(resultUrl: string) {
  return {
    task_id: 't1',
    tool: 'translate',
    status: 'done' as const,
    progress: 100,
    result_url: resultUrl,
    error: null,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ToolPage', () => {
  it('shows the not-found page for an unknown slug', () => {
    renderSlug('does-not-exist');
    expect(screen.getByRole('heading', { name: 'Ferramenta não encontrada' })).toBeInTheDocument();
  });

  it('surfaces Louder as a client-side link instead of rebuilding it', () => {
    renderSlug('louder');
    const link = screen.getByRole('link', { name: /abrir louder/i });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('href')).toMatch(/louder/);
  });

  it('renders the Translator form with the target language select', () => {
    renderSlug('translate');
    expect(screen.getByRole('heading', { name: 'Translator' })).toBeInTheDocument();
    expect(screen.getByLabelText('Texto')).toBeInTheDocument();
    expect(screen.getByLabelText('Idioma de destino')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /processar/i })).toBeDisabled();
  });

  it('submits a text job, polls it and renders the translated result', async () => {
    createTextJobMock.mockResolvedValue({ task_id: 't1', tool: 'translate', status: 'queued' });
    pollJobMock.mockResolvedValue(doneJob('memory://tmp/result.txt'));
    fetchTextMock.mockResolvedValue('Olá, mundo!');

    const user = userEvent.setup();
    renderSlug('translate');

    await user.type(screen.getByLabelText('Texto'), 'Hello, world!');
    await user.click(screen.getByRole('button', { name: /processar/i }));

    expect(await screen.findByText('Olá, mundo!')).toBeInTheDocument();
    expect(createTextJobMock).toHaveBeenCalledWith(
      'translate',
      'Hello, world!',
      expect.objectContaining({ target: 'en', tone: 'neutral' }),
      expect.anything(),
    );
    expect(pollJobMock).toHaveBeenCalledWith(
      'translate',
      't1',
      expect.objectContaining({ onUpdate: expect.any(Function) }),
    );
  });

  it('shows the gateway error message when the job creation fails', async () => {
    createTextJobMock.mockRejectedValue(new ApiError('endpoint quebrou', 500));

    const user = userEvent.setup();
    renderSlug('translate');

    await user.type(screen.getByLabelText('Texto'), 'Hello');
    await user.click(screen.getByRole('button', { name: /processar/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('endpoint quebrou');
  });

  it('shows a clear notice when the AI provider is unavailable (503)', async () => {
    createTextJobMock.mockRejectedValue(new ApiError('provider unavailable', 503));

    const user = userEvent.setup();
    renderSlug('feedback');

    await user.type(screen.getByLabelText('Texto'), 'Avaliação');
    await user.click(screen.getByRole('button', { name: /processar/i }));

    expect(await screen.findByText(/provedor de ia não está configurado/i)).toBeInTheDocument();
  });

  it('uploads a file for file-based tools', async () => {
    createFileJobMock.mockResolvedValue({ task_id: 't2', tool: 'ocr', status: 'queued' });
    pollJobMock.mockResolvedValue({ ...doneJob('memory://tmp/result.json'), tool: 'ocr' });
    fetchTextMock.mockResolvedValue('{}');

    const user = userEvent.setup();
    renderSlug('ocr');

    const file = new File([new Uint8Array([1, 2, 3])], 'scan.png', { type: 'image/png' });
    await user.upload(screen.getByLabelText('Imagem'), file);
    await user.click(screen.getByRole('button', { name: /processar/i }));

    expect(createFileJobMock).toHaveBeenCalledWith(
      'ocr',
      file,
      expect.any(Object),
      expect.anything(),
    );
  });
});
