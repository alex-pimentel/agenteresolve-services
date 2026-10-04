import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  createFileJob,
  createTextJob,
  fetchText,
  getJob,
  isUnimplemented,
  pollJob,
} from './api';

interface FakeResponseInit {
  status?: number;
  body?: unknown;
  jsonThrows?: boolean;
}

function fakeResponse({ status = 200, body = {}, jsonThrows = false }: FakeResponseInit): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      if (jsonThrows) {
        throw new Error('not json');
      }
      return body;
    },
    text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
  } as unknown as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('createTextJob', () => {
  it('posts JSON and returns the created job', async () => {
    fetchMock.mockResolvedValueOnce(
      fakeResponse({
        status: 202,
        body: { task_id: 't1', tool: 'translate', status: 'queued' },
      }),
    );

    const result = await createTextJob('translate', 'Hello', { target: 'pt', tone: 'neutral' });

    expect(result).toEqual({ task_id: 't1', tool: 'translate', status: 'queued' });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/translate\/$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({
      text: 'Hello',
      target: 'pt',
      tone: 'neutral',
    });
  });

  it('throws an ApiError with the gateway detail on failure', async () => {
    fetchMock.mockResolvedValueOnce(
      fakeResponse({ status: 501, body: { detail: 'not implemented yet' } }),
    );

    let caught: unknown;
    try {
      await createTextJob('feedback', 'x');
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(501);
    expect((caught as ApiError).message).toBe('not implemented yet');
    expect(isUnimplemented(caught)).toBe(true);
  });

  it('falls back to a generic message when the body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(fakeResponse({ status: 500, jsonThrows: true }));
    await expect(createTextJob('translate', 'x')).rejects.toThrow(
      'Falha na requisição (HTTP 500).',
    );
  });

  it('rejects a response without task_id', async () => {
    fetchMock.mockResolvedValueOnce(fakeResponse({ status: 202, body: {} }));
    await expect(createTextJob('translate', 'x')).rejects.toThrow(/task_id ausente/);
  });
});

describe('createFileJob', () => {
  it('posts multipart form data with options', async () => {
    fetchMock.mockResolvedValueOnce(
      fakeResponse({ status: 202, body: { task_id: 't2', tool: 'ocr', status: 'queued' } }),
    );

    const file = new File([new Uint8Array([1, 2, 3])], 'scan.png', { type: 'image/png' });
    const result = await createFileJob('ocr', file, { lang: 'por' });

    expect(result.task_id).toBe('t2');
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get('lang')).toBe('por');
    expect((form.get('file') as File).name).toBe('scan.png');
  });
});

describe('getJob', () => {
  it('returns the job payload', async () => {
    const job = {
      task_id: 't1',
      tool: 'translate',
      status: 'done',
      progress: 100,
      result_url: 'memory://tmp/result.txt',
      error: null,
    };
    fetchMock.mockResolvedValueOnce(fakeResponse({ body: job }));
    await expect(getJob('translate', 't1')).resolves.toEqual(job);
  });

  it('throws on 404', async () => {
    fetchMock.mockResolvedValueOnce(fakeResponse({ status: 404, body: { detail: 'missing' } }));
    await expect(getJob('translate', 'nope')).rejects.toBeInstanceOf(ApiError);
  });
});

describe('pollJob', () => {
  it('resolves once the job is done and reports updates', async () => {
    const processing = {
      task_id: 't1',
      tool: 'translate',
      status: 'processing',
      progress: 50,
      result_url: null,
      error: null,
    };
    const done = { ...processing, status: 'done', progress: 100, result_url: 'memory://r.txt' };
    fetchMock
      .mockResolvedValueOnce(fakeResponse({ body: processing }))
      .mockResolvedValueOnce(fakeResponse({ body: done }));

    const onUpdate = vi.fn();
    const job = await pollJob('translate', 't1', { intervalMs: 1, onUpdate });

    expect(job.status).toBe('done');
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it('returns an errored job instead of throwing', async () => {
    const errored = {
      task_id: 't1',
      tool: 'translate',
      status: 'error',
      progress: 0,
      result_url: null,
      error: 'boom',
    };
    fetchMock.mockResolvedValueOnce(fakeResponse({ body: errored }));

    await expect(pollJob('translate', 't1', { intervalMs: 1 })).resolves.toEqual(errored);
  });

  it('times out when the job never finishes', async () => {
    const processing = {
      task_id: 't1',
      tool: 'translate',
      status: 'processing',
      progress: 10,
      result_url: null,
      error: null,
    };
    fetchMock.mockResolvedValue(fakeResponse({ body: processing }));

    await expect(pollJob('translate', 't1', { intervalMs: 1, timeoutMs: 0 })).rejects.toMatchObject(
      {
        status: 408,
      },
    );
  });

  it('aborts when the signal is already aborted', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(pollJob('translate', 't1', { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('fetchText', () => {
  it('returns the response body as text', async () => {
    fetchMock.mockResolvedValueOnce(fakeResponse({ body: 'Olá, mundo!' }));
    await expect(fetchText('memory://r.txt')).resolves.toBe('Olá, mundo!');
  });
});
