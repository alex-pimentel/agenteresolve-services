import { Button, Card, CardContent, CardHeader, CardTitle, ServiceShell } from '@agenteresolve/ui';
import { ExternalLink } from 'lucide-react';

import { StateMessage } from '../components/StateMessage';
import type { ToolConfig } from '../data/tools';
import { CLERK_PUBLISHABLE_KEY, LOUDER_URL } from '../lib/env';
import { SERVICE_NAV } from '../lib/nav';

export interface LouderPageProps {
  tool: ToolConfig;
}

/**
 * Client-side surface for Louder. The reader itself lives in the standalone
 * app; here we only surface it inside the shared Service Shell.
 */
export function LouderPage({ tool }: LouderPageProps) {
  return (
    <ServiceShell
      publishableKey={CLERK_PUBLISHABLE_KEY}
      services={SERVICE_NAV}
      title={tool.name}
      description={tool.description}
    >
      <Card className="gap-5">
        <CardHeader>
          <CardTitle>Leia em voz alta, sem upload</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            O Louder é uma ferramenta 100% client-side: o PDF ou texto é processado no seu navegador
            com Web Speech + PDF.js. Nenhum arquivo é enviado a servidores.
          </p>
          <StateMessage tone="info" title="Nada sai do seu dispositivo">
            A leitura usa as vozes do seu sistema operacional. Preferências ficam apenas no seu
            navegador.
          </StateMessage>
          <div>
            <Button asChild size="lg">
              <a href={LOUDER_URL} target="_blank" rel="noreferrer">
                Abrir Louder
                <ExternalLink />
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </ServiceShell>
  );
}
