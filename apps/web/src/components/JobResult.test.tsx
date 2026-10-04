import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getTool, type ToolConfig } from '../data/tools';
import type { Job } from '../lib/api';
import { JobResult } from './JobResult';

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>();
  return { ...actual, fetchText: vi.fn() };
});

import * as api from '../lib/api';

const fetchTextMock = vi.mocked(api.fetchText);

function tool(slug: string): ToolConfig {
  const found = getTool(slug);
  if (!found) {
    throw new Error(`missing tool ${slug}`);
  }
  return found;
}

function job(overrides: Partial<Job> = {}): Job {
  return {
    task_id: 't1',
    tool: 'translate',
    status: 'done',
    progress: 100,
    result_url: 'memory://tmp/result',
    error: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('JobResult', () => {
  it('renders an error state from the job', () => {
    render(<JobResult tool={tool('translate')} job={job({ status: 'error', error: 'boom' })} />);
    expect(screen.getByRole('alert')).toHaveTextContent('boom');
  });

  it('renders a loading state while processing', () => {
    render(
      <JobResult tool={tool('translate')} job={job({ status: 'processing', result_url: null })} />,
    );
    expect(screen.getByText('Processando…')).toBeInTheDocument();
  });

  it('fetches and renders a text result', async () => {
    fetchTextMock.mockResolvedValue('Olá, mundo!');
    render(<JobResult tool={tool('translate')} job={job()} />);
    expect(await screen.findByText('Olá, mundo!')).toBeInTheDocument();
  });

  it('pretty-prints a JSON result', async () => {
    fetchTextMock.mockResolvedValue('{"answer":42}');
    render(<JobResult tool={tool('docuextract')} job={job()} />);
    expect(await screen.findByText(/"answer": 42/)).toBeInTheDocument();
  });

  it('renders an audio result', () => {
    const { container } = render(<JobResult tool={tool('tts')} job={job()} />);
    expect(container.querySelector('audio')).toBeInTheDocument();
  });

  it('renders an image result', () => {
    render(<JobResult tool={tool('anonymize')} job={job()} />);
    expect(screen.getByRole('img', { name: 'Resultado do processamento' })).toBeInTheDocument();
  });

  it('renders a download result', () => {
    const downloadTool: ToolConfig = { ...tool('docuextract'), result: 'download' };
    render(<JobResult tool={downloadTool} job={job()} />);
    expect(screen.getByText('Resultado pronto')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /baixar/i })).toBeInTheDocument();
  });

  it('falls back to a download notice when the preview fails', async () => {
    fetchTextMock.mockRejectedValue(new Error('cors'));
    render(<JobResult tool={tool('translate')} job={job()} />);
    await waitFor(() =>
      expect(screen.getByText(/não foi possível pré-visualizar/i)).toBeInTheDocument(),
    );
  });
});
