import * as React from 'react';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ServiceShell,
} from '@agenteresolve/ui';
import { Sparkles } from 'lucide-react';
import { useParams } from 'react-router-dom';

import { JobResult } from '../components/JobResult';
import { StateMessage } from '../components/StateMessage';
import { ToolInput } from '../components/ToolInput';
import { formatBytes, getTool, type ToolConfig } from '../data/tools';
import { createFileJob, createTextJob, isUnimplemented, pollJob, type Job } from '../lib/api';
import { CLERK_PUBLISHABLE_KEY } from '../lib/env';
import { SERVICE_NAV } from '../lib/nav';
import { LouderPage } from './LouderPage';
import { NotFoundPage } from './NotFoundPage';

type Phase = 'idle' | 'running';

function initialOptions(tool: ToolConfig): Record<string, string> {
  const values: Record<string, string> = {};
  for (const option of tool.options ?? []) {
    values[option.name] = option.defaultValue ?? option.choices?.[0]?.value ?? '';
  }
  return values;
}

function GatewayToolPage({ tool }: { tool: ToolConfig }) {
  const [text, setText] = React.useState('');
  const [file, setFile] = React.useState<File | null>(null);
  const [optionValues, setOptionValues] = React.useState<Record<string, string>>(() =>
    initialOptions(tool),
  );
  const [job, setJob] = React.useState<Job | null>(null);
  const [phase, setPhase] = React.useState<Phase>('idle');
  const [error, setError] = React.useState<string | null>(null);
  const [betaNotice, setBetaNotice] = React.useState<string | null>(null);
  const controllerRef = React.useRef<AbortController | null>(null);

  React.useEffect(() => () => controllerRef.current?.abort(), []);

  const isText = tool.input === 'text';
  const running = phase === 'running';
  const canSubmit = !running && (isText ? text.trim().length > 0 : file !== null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    setError(null);
    setBetaNotice(null);
    setJob(null);
    setPhase('running');

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const created = isText
        ? await createTextJob(tool.slug, text, optionValues, controller.signal)
        : await createFileJob(tool.slug, file as File, optionValues, controller.signal);

      const finished = await pollJob(tool.slug, created.task_id, {
        signal: controller.signal,
        onUpdate: setJob,
      });
      setJob(finished);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      if (isUnimplemented(err)) {
        setBetaNotice(
          'Esta ferramenta está em beta e o endpoint ainda não está disponível no gateway.',
        );
      } else {
        setError(err instanceof Error ? err.message : 'Erro inesperado ao processar.');
      }
    } finally {
      setPhase('idle');
    }
  }

  return (
    <ServiceShell
      publishableKey={CLERK_PUBLISHABLE_KEY}
      services={SERVICE_NAV}
      title={tool.name}
      description={tool.description}
    >
      {tool.note ? (
        <StateMessage tone="info" title="Aviso" className="mb-6">
          {tool.note}
        </StateMessage>
      ) : null}

      {tool.beta ? (
        <StateMessage tone="info" title="Ferramenta em beta" className="mb-6">
          O endpoint ainda não está implementado no gateway (responde 501). A interface já está
          pronta para quando o serviço entrar no ar.
        </StateMessage>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="gap-5">
          <CardHeader className="flex-row items-center justify-between gap-2">
            <CardTitle>Entrada</CardTitle>
            {tool.beta ? (
              <Badge variant="outline">Beta</Badge>
            ) : (
              <Badge variant="secondary">Disponível</Badge>
            )}
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
              <ToolInput
                tool={tool}
                text={text}
                onTextChange={setText}
                file={file}
                onFileChange={setFile}
                optionValues={optionValues}
                onOptionChange={(name, value) =>
                  setOptionValues((current) => ({ ...current, [name]: value }))
                }
                disabled={running}
              />

              {error ? (
                <StateMessage tone="error" title="Erro">
                  {error}
                </StateMessage>
              ) : null}

              {betaNotice ? (
                <StateMessage tone="info" title="Ferramenta em beta">
                  {betaNotice}
                </StateMessage>
              ) : null}

              <div className="flex flex-wrap items-center gap-3">
                <Button type="submit" disabled={!canSubmit}>
                  <Sparkles />
                  {running ? 'Processando…' : 'Processar'}
                </Button>
                <span className="text-xs text-muted-foreground">
                  Limite {formatBytes(tool.maxBytes)} · resultado expira em 24h.
                </span>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          {job ? (
            <JobResult tool={tool} job={job} />
          ) : (
            <Card className="h-full gap-3">
              <CardHeader>
                <CardTitle>Saída</CardTitle>
                <CardDescription>
                  Envie a entrada ao lado para ver o resultado aqui.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  O conteúdo é processado de forma efêmera e removido automaticamente em 24 horas.
                  Nada é persistido no banco de dados.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </ServiceShell>
  );
}

export function ToolPage() {
  const { slug } = useParams<{ slug: string }>();
  const tool = slug ? getTool(slug) : undefined;

  if (!tool) {
    return <NotFoundPage />;
  }

  if (tool.route === 'client') {
    return <LouderPage tool={tool} />;
  }

  return <GatewayToolPage tool={tool} />;
}
