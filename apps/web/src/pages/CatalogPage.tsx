import { Badge, ServiceShell } from '@agenteresolve/ui';

import { CATEGORIES, TOOLS, toolsByCategory } from '../data/tools';
import { ToolCard } from '../components/ToolCard';
import { CLERK_PUBLISHABLE_KEY } from '../lib/env';
import { SERVICE_NAV } from '../lib/nav';

export function CatalogPage() {
  const available = TOOLS.filter((tool) => !tool.beta).length;

  return (
    <ServiceShell
      publishableKey={CLERK_PUBLISHABLE_KEY}
      services={SERVICE_NAV}
      title="Ferramentas de IA"
      description="Um catálogo único de ferramentas de texto, visão e áudio. Sem persistir o seu conteúdo: entradas e resultados expiram em 24h."
    >
      <p className="mb-10 text-sm text-muted-foreground">
        {TOOLS.length} ferramentas · {available} disponíveis agora · o restante em beta.
      </p>

      <div className="flex flex-col gap-14">
        {CATEGORIES.map((category) => {
          const tools = toolsByCategory(category.id);
          if (tools.length === 0) {
            return null;
          }
          return (
            <section
              key={category.id}
              id={category.id}
              aria-labelledby={`category-${category.id}`}
              className="flex flex-col gap-5"
            >
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-3">
                  <h2
                    id={`category-${category.id}`}
                    className="text-xl font-semibold tracking-tight text-foreground"
                  >
                    {category.title}
                  </h2>
                  <Badge variant="outline">{tools.length}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{category.description}</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {tools.map((tool) => (
                  <ToolCard key={tool.slug} tool={tool} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </ServiceShell>
  );
}
