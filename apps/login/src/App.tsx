import * as React from 'react';
import { useAuth, useUser } from '@clerk/clerk-react';
import { Loader2 } from 'lucide-react';
import { AuthProvider, Button, Card, CardContent, ServiceShell } from '@agenteresolve/ui';
import { SignIn } from '@clerk/clerk-react';

import { CLERK_PUBLISHABLE_KEY } from './lib/env';
import { resolveRedirect } from './lib/redirect';
import { exchangeSession } from './lib/session';
import { StateMessage } from './components/StateMessage';

function readRedirect(): string {
  return resolveRedirect(new URLSearchParams(window.location.search).get('redirect'));
}

/** After Clerk sign-in: exchange JWT for a gateway token and return to the service. */
function SessionExchange({ redirect }: { redirect: string }) {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [error, setError] = React.useState<string | null>(null);
  const startedRef = React.useRef(false);

  React.useEffect(() => {
    if (startedRef.current) {
      return;
    }
    startedRef.current = true;
    const controller = new AbortController();
    (async () => {
      try {
        const clerkToken = await getToken();
        if (!clerkToken) {
          throw new Error('Não foi possível obter o token do Clerk.');
        }
        const session = await exchangeSession(clerkToken, controller.signal);
        const target = new URL(redirect);
        target.hash = new URLSearchParams({
          access_token: session.access_token,
          expires_at: String(session.expires_at),
        }).toString();
        window.location.replace(target.toString());
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        setError(err instanceof Error ? err.message : 'Erro inesperado ao criar sessão.');
      }
    })();
    return () => controller.abort();
  }, [getToken, redirect]);

  return (
    <Card>
      <CardContent>
        {error ? (
          <StateMessage tone="error" title="Erro">
            {error}
          </StateMessage>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="animate-spin" />
            Olá, {user?.firstName ?? 'bem-vindo(a)'}! Criando sua sessão e voltando para a
            ferramenta…
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function LoginBody() {
  const [redirect] = React.useState(readRedirect);
  const { isSignedIn, isLoaded } = useAuth();
  const [loadTimedOut, setLoadTimedOut] = React.useState(false);

  // Clerk loads its JS from the Clerk Frontend API. If that host is
  // unreachable (DNS, offline), `isLoaded` never flips and the page would
  // spin forever — surface an error with retry instead.
  React.useEffect(() => {
    if (isLoaded) {
      return;
    }
    const timer = window.setTimeout(() => setLoadTimedOut(true), 15_000);
    return () => window.clearTimeout(timer);
  }, [isLoaded]);

  if (!isLoaded) {
    if (!loadTimedOut) {
      return (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="animate-spin" /> Carregando…
        </p>
      );
    }
    return (
      <div className="flex max-w-md flex-col items-center gap-4">
        <StateMessage tone="error" title="Não foi possível carregar o login">
          O serviço de autenticação não respondeu. Verifique sua conexão com a internet e
          tente novamente.
        </StateMessage>
        <Button type="button" onClick={() => window.location.reload()}>
          Tentar novamente
        </Button>
      </div>
    );
  }

  if (isSignedIn) {
    return <SessionExchange redirect={redirect} />;
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold">Entrar na Agenteresolve</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Um login para todas as ferramentas. Novas contas ganham{' '}
          <strong>50 créditos</strong> de boas-vindas.
        </p>
      </div>
      <SignIn
        routing="hash"
        afterSignInUrl={window.location.pathname + window.location.search}
        appearance={{ elements: { rootBox: 'mx-auto' } }}
      />
    </div>
  );
}

export function App() {
  if (!CLERK_PUBLISHABLE_KEY) {
    return (
      <ServiceShell title="Entrar" description="Login central da Agenteresolve">
        <StateMessage tone="error" title="Login indisponível">
          A chave do Clerk não foi configurada neste build (VITE_CLERK_PUBLISHABLE_KEY). Volte à
          ferramenta e tente novamente mais tarde.
        </StateMessage>
        <Button type="button" onClick={() => window.history.back()}>
          Voltar
        </Button>
      </ServiceShell>
    );
  }

  return (
    <AuthProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      <ServiceShell
        publishableKey={CLERK_PUBLISHABLE_KEY}
        title="Entrar"
        description="Login central da Agenteresolve"
      >
        <LoginBody />
      </ServiceShell>
    </AuthProvider>
  );
}
