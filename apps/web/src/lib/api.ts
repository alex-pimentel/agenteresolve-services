import { API_BASE } from './env';

export type JobStatus = 'queued' | 'processing' | 'done' | 'error';

export interface Job {
  task_id: string;
  tool: string;
  status: JobStatus;
  progress: number;
  result_url: string | null;
  error: string | null;
}

export interface CreateJobResponse {
  task_id: string;
  tool: string;
  status: JobStatus;
}

export type ParamValue = string | number | boolean;
export type JobParams = Record<string, ParamValue>;

/** Error carrying the HTTP status and the gateway's `detail` message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** `true` when the tool is registered at the gateway but not implemented yet. */
export function isUnimplemented(error: unknown): boolean {
  return error instanceof ApiError && error.status === 501;
}

export function isProviderUnavailable(error: unknown): boolean {
  return error instanceof ApiError && error.status === 503;
}

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
    }
  } catch {
    // Body was not JSON; fall through to the generic message.
  }
  return `Falha na requisição (HTTP ${response.status}).`;
}

async function handleCreated(response: Response): Promise<CreateJobResponse> {
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  const data = (await response.json()) as Partial<CreateJobResponse>;
  if (!data.task_id) {
    throw new ApiError('Resposta inválida do gateway: task_id ausente.', response.status);
  }
  return {
    task_id: data.task_id,
    tool: data.tool ?? '',
    status: data.status ?? 'queued',
  };
}

/** Create a text job (`POST /api/{slug}/` with a JSON body). */
export async function createTextJob(
  slug: string,
  text: string,
  params: JobParams = {},
  signal?: AbortSignal,
): Promise<CreateJobResponse> {
  const response = await fetch(apiUrl(`/api/${slug}/`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, ...params }),
    signal,
  });
  return handleCreated(response);
}

/** Create a file job (`POST /api/{slug}/` with `multipart/form-data`). */
export async function createFileJob(
  slug: string,
  file: File,
  params: JobParams = {},
  signal?: AbortSignal,
): Promise<CreateJobResponse> {
  const form = new FormData();
  form.append('file', file, file.name);
  for (const [key, value] of Object.entries(params)) {
    form.append(key, String(value));
  }
  const response = await fetch(apiUrl(`/api/${slug}/`), {
    method: 'POST',
    body: form,
    signal,
  });
  return handleCreated(response);
}

/** Fetch a job (`GET /api/{slug}/{task_id}`). */
export async function getJob(slug: string, taskId: string, signal?: AbortSignal): Promise<Job> {
  const response = await fetch(apiUrl(`/api/${slug}/${taskId}`), { signal });
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  return (await response.json()) as Job;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, ms);

    const onAbort = () => {
      cleanup();
      reject(new DOMException('Aborted', 'AbortError'));
    };

    function cleanup(): void {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    }

    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export interface PollOptions {
  intervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
  onUpdate?: (job: Job) => void;
}

/** Poll a job until it reaches `done` or `error` (or times out). */
export async function pollJob(
  slug: string,
  taskId: string,
  options: PollOptions = {},
): Promise<Job> {
  const { intervalMs = 1500, timeoutMs = 180_000, signal, onUpdate } = options;
  const deadline = Date.now() + timeoutMs;

  for (;;) {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError');
    }
    const job = await getJob(slug, taskId, signal);
    onUpdate?.(job);
    if (job.status === 'done' || job.status === 'error') {
      return job;
    }
    if (Date.now() >= deadline) {
      throw new ApiError('Tempo limite de processamento excedido.', 408);
    }
    await delay(intervalMs, signal);
  }
}

/** Fetch a result as text (used to preview `text`/`json` results). */
export async function fetchText(url: string, signal?: AbortSignal): Promise<string> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  return response.text();
}
