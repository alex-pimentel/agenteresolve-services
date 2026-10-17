import { Button, Card, CardContent, CardHeader, CardTitle, ServiceShell } from '@agenteresolve/ui';
import { ExternalLink } from 'lucide-react';

import { StateMessage } from '../components/StateMessage';
import type { ToolConfig } from '../data/tools';
import { CLERK_PUBLISHABLE_KEY, clientAppUrl } from '../lib/env';
import { SERVICE_NAV } from '../lib/nav';

export interface ClientAppPageProps {
  tool: ToolConfig;
}

/**
 * Surface for a client-side tool. The app itself runs standalone in the user's
 * browser; here we only present it inside the shared Service Shell with the
 * direct link to the standalone app.
 */
export function ClientAppPage({ tool }: ClientAppPageProps) {
  const appUrl = clientAppUrl(tool.slug);

  return (
    <ServiceShell
      publishableKey={CLERK_PUBLISHABLE_KEY}
      services={SERVICE_NAV}
      title={tool.name}
      description={tool.description}
    >
      <Card className="gap-5">
        <CardHeader>
          <CardTitle>Roda no seu navegador, sem upload</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            {tool.name} é 100% client-side: o processamento acontece no seu dispositivo e nenhum
            arquivo é enviado a servidores.
          </p>
          {tool.note ? (
            <StateMessage tone="info" title="Nada sai do seu dispositivo">
              {tool.note}
            </StateMessage>
          ) : null}
          {appUrl ? (
            <div>
              <Button asChild size="lg">
                <a href={appUrl} target="_blank" rel="noreferrer">
                  Abrir {tool.name}
                  <ExternalLink />
                </a>
              </Button>
            </div>
          ) : (
            <StateMessage tone="error" title="App standalone não publicado">
              Esta ferramenta ainda não tem URL pública configurada.
            </StateMessage>
          )}
        </CardContent>
      </Card>
    </ServiceShell>
  );
}
