const DEFAULT_API_BASE = 'https://api.agenteresolve.com.br';

/** Base URL of the AI services gateway (no trailing slash). */
export const API_BASE: string = (
  import.meta.env.VITE_API_BASE?.trim() || DEFAULT_API_BASE
).replace(/\/+$/, '');

/** Clerk publishable key — required in this app (the only Clerk frontend). */
export const CLERK_PUBLISHABLE_KEY: string | undefined =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim() || undefined;

/** Extra allowed redirect origins (comma-separated env). */
export const ALLOWED_REDIRECT_ORIGINS: string[] = (import.meta.env.VITE_ALLOWED_REDIRECT_ORIGINS ?? '')
  .split(',')
  .map((origin) => origin.trim().replace(/\/+$/, ''))
  .filter((origin) => origin.length > 0);
