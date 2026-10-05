import { render, screen } from '@testing-library/react';
import * as React from 'react';
import { describe, expect, it, vi } from 'vitest';

let providerMounts = 0;

vi.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ isLoaded: true, isSignedIn: false }),
  useUser: () => ({ user: null }),
  useClerk: () => ({}),
  SignIn: () => null,
  UserButton: () => null,
  ClerkProvider: ({ children }: { children: React.ReactNode }) => {
    providerMounts += 1;
    if (providerMounts > 1) {
      throw new Error(
        "You've added multiple <ClerkProvider> components in your React component tree.",
      );
    }
    return <>{children}</>;
  },
}));

describe('App Clerk providers', () => {
  it('mounts exactly one ClerkProvider', async () => {
    // import.meta.env is snapshotted at module evaluation, so the key must be
    // stubbed before importing the App module.
    vi.stubEnv('VITE_CLERK_PUBLISHABLE_KEY', 'pk_test_single_provider');
    const { App } = await import('./App');
    providerMounts = 0;
    render(<App />);
    expect(providerMounts).toBe(1);
    expect(screen.getByText('Entrar na Agenteresolve')).toBeTruthy();
    vi.unstubAllEnvs();
  });
});
