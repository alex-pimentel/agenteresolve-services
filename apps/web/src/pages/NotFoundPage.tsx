import { Button, ServiceShell } from '@agenteresolve/ui';
import { Link } from 'react-router-dom';

import { CLERK_PUBLISHABLE_KEY } from '../lib/env';
import { SERVICE_NAV } from '../lib/nav';

export function NotFoundPage() {
  return (
    <ServiceShell
      publishableKey={CLERK_PUBLISHABLE_KEY}
      services={SERVICE_NAV}
      title="Ferramenta não encontrada"
      description="A rota solicitada não existe no catálogo. Verifique o endereço ou volte para a lista completa."
    >
      <Button asChild variant="outline">
        <Link to="/">Voltar ao catálogo</Link>
      </Button>
    </ServiceShell>
  );
}
