import { ALLOWED_REDIRECT_ORIGINS } from './env';

const PARENT_DOMAIN = 'agenteresolve.com.br';

function isLocalhost(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

function isAllowedHost(hostname: string): boolean {
  const host = hostname.toLowerCase();
  return host === PARENT_DOMAIN || host.endsWith(`.${PARENT_DOMAIN}`) || isLocalhost(host);
}

/**
 * Validate the `?redirect=` target. Only same-eTLD+1 origins
 * (`*.agenteresolve.com.br`), localhost and the extra env allowlist are
 * accepted — anything else falls back to the tools catalog. This prevents
 * open-redirect theft of the session token passed in the URL fragment.
 */
export function resolveRedirect(raw: string | null): string {
  const fallback = 'https://tools.agenteresolve.com.br';
  if (!raw) {
    return fallback;
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return fallback;
  }
  if (url.protocol !== 'https:' && !isLocalhost(url.hostname)) {
    return fallback;
  }
  if (isAllowedHost(url.hostname)) {
    return url.toString();
  }
  if (ALLOWED_REDIRECT_ORIGINS.includes(url.origin)) {
    return url.toString();
  }
  return fallback;
}

/** Build the login URL for a service, preserving where to return afterwards. */
export function buildLoginUrl(serviceReturnUrl: string): string {
  const login = new URL(window.location.origin);
  login.pathname = '/';
  login.searchParams.set('redirect', serviceReturnUrl);
  return login.toString();
}
