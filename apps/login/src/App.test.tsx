import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginBody } from './App';

vi.mock('@clerk/clerk-react', () => ({
  // Simulates the Clerk JS failing to load (e.g. Frontend API DNS down):
  // `isLoaded` never flips to true.
  useAuth: () => ({ isLoaded: false, isSignedIn: false }),
  useUser: () => ({ user: null }),
  SignIn: () => null,
}));

describe('LoginBody Clerk load failure', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('shows a spinner while Clerk is loading', () => {
    render(<LoginBody />);
    expect(screen.getByText('Carregando…')).toBeTruthy();
  });

  it('shows an error with retry after the load timeout', () => {
    render(<LoginBody />);
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(screen.getByText('Não foi possível carregar o login')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeTruthy();
  });

  it('retry reloads the page', () => {
    const reload = vi.fn();
    Object.defineProperty(window, 'location', { value: { ...window.location, reload } });
    render(<LoginBody />);
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
