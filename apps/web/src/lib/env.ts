const DEFAULT_API_BASE = 'https://api.agenteresolve.com.br';
const DEFAULT_LOUDER_URL = 'https://louder.agenteresolve.com.br';
const DEFAULT_QRCODE_URL = 'https://qrcode.agenteresolve.com.br';
const DEFAULT_IMPOSITION_URL = 'https://imposition.agenteresolve.com.br';

/** Base URL of the AI services gateway (no trailing slash). */
export const API_BASE: string = (import.meta.env.VITE_API_BASE?.trim() || DEFAULT_API_BASE).replace(
  /\/+$/,
  '',
);

/** Standalone client-side apps surfaced by the catalog, keyed by tool slug. */
export const CLIENT_APP_URLS: Readonly<Record<string, string>> = {
  louder: import.meta.env.VITE_LOUDER_URL?.trim() || DEFAULT_LOUDER_URL,
  qrcode: import.meta.env.VITE_QRCODE_URL?.trim() || DEFAULT_QRCODE_URL,
  imposition: import.meta.env.VITE_IMPOSITION_URL?.trim() || DEFAULT_IMPOSITION_URL,
};

/** URL of the standalone app behind a client-side tool, when one is published. */
export function clientAppUrl(slug: string): string | undefined {
  return CLIENT_APP_URLS[slug];
}

/** Optional Clerk publishable key; when absent the UI degrades gracefully. */
export const CLERK_PUBLISHABLE_KEY: string | undefined =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim() || undefined;
