import { describe, expect, it } from 'vitest';

import { resolveRedirect } from './redirect';

describe('resolveRedirect', () => {
  it('accepts tool subdomains', () => {
    expect(resolveRedirect('https://translate.agenteresolve.com.br/auth/callback')).toBe(
      'https://translate.agenteresolve.com.br/auth/callback',
    );
  });

  it('accepts the parent domain and localhost', () => {
    expect(resolveRedirect('https://agenteresolve.com.br/pt')).toBe('https://agenteresolve.com.br/pt');
    expect(resolveRedirect('http://localhost:5173/auth/callback')).toBe(
      'http://localhost:5173/auth/callback',
    );
  });

  it('rejects foreign origins, schemes and garbage', () => {
    expect(resolveRedirect('https://evil.com/steal')).toBe('https://tools.agenteresolve.com.br');
    expect(resolveRedirect('http://translate.agenteresolve.com.br/x')).toBe(
      'https://tools.agenteresolve.com.br',
    );
    expect(resolveRedirect('javascript:alert(1)')).toBe('https://tools.agenteresolve.com.br');
    expect(resolveRedirect('not-a-url')).toBe('https://tools.agenteresolve.com.br');
    expect(resolveRedirect(null)).toBe('https://tools.agenteresolve.com.br');
  });
});
