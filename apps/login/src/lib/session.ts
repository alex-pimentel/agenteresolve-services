import { API_BASE } from './env';

export interface GatewaySession {
  access_token: string;
  expires_at: number;
  clerk_id: string;
  balance: number | null;
}

/** Exchange the Clerk JWT for a long-lived gateway session token. */
export async function exchangeSession(clerkToken: string, signal?: AbortSignal): Promise<GatewaySession> {
  const response = await fetch(`${API_BASE}/api/auth/session`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${clerkToken}` },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Falha ao criar sessão (${response.status}). Tente novamente.`);
  }
  return (await response.json()) as GatewaySession;
}
