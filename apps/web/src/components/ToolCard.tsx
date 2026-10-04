import { Badge, Card, cn } from '@agenteresolve/ui';
import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { formatBytes, type ToolConfig } from '../data/tools';

export interface ToolCardProps {
  tool: ToolConfig;
}

export function ToolCard({ tool }: ToolCardProps) {
  const Icon = tool.icon;
  const meta = tool.category === 'client' ? 'Client-side' : `Limite ${formatBytes(tool.maxBytes)}`;

  return (
    <Link
      to={`/${tool.slug}`}
      data-testid="tool-card"
      data-slug={tool.slug}
      className="group rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <Card className="h-full gap-4 transition-colors group-hover:border-brand/60 group-hover:bg-surface-strong/60">
        <div className="flex items-start justify-between gap-3">
          <span
            aria-hidden
            className="flex size-11 items-center justify-center rounded-xl bg-brand-gradient text-brand-foreground shadow-sm"
          >
            <Icon className="size-5" />
          </span>
          <div className="flex flex-wrap justify-end gap-1.5">
            {tool.beta ? <Badge variant="outline">Beta</Badge> : null}
            {tool.category === 'client' ? <Badge variant="secondary">No navegador</Badge> : null}
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-1.5">
          <h3 className="text-base font-semibold tracking-tight text-foreground">{tool.name}</h3>
          <p className="text-sm text-muted-foreground">{tool.description}</p>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{meta}</span>
          <span className="inline-flex items-center gap-1 font-medium text-brand">
            Abrir
            <ArrowRight
              className={cn('size-3.5 transition-transform group-hover:translate-x-0.5')}
            />
          </span>
        </div>
      </Card>
    </Link>
  );
}
