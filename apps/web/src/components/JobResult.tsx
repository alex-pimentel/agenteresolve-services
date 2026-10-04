import * as React from 'react';
import { Button, Card, CardContent, CardHeader, CardTitle } from '@agenteresolve/ui';
import { Download, Loader2 } from 'lucide-react';

import type { ToolConfig } from '../data/tools';
import { fetchText, type Job } from '../lib/api';
import { StateMessage } from './StateMessage';

export interface JobResultProps {
  tool: ToolConfig;
  job: Job;
}

interface AsyncText {
  content: string | null;
  error: boolean;
  loading: boolean;
}

interface AsyncTextState {
  url: string;
  content: string | null;
  error: boolean;
}

/**
 * Fetches an arbitrary result URL as text, resetting implicitly when the URL
 * changes (state is keyed by URL rather than cleared inside the effect).
 */
function useAsyncText(url: string): AsyncText {
  const [state, setState] = React.useState<AsyncTextState | null>(null);

  React.useEffect(() => {
    const controller = new AbortController();
    fetchText(url, controller.signal)
      .then((content) => {
        setState({ url, content, error: false });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        setState({ url, content: null, error: true });
      });
    return () => controller.abort();
  }, [url]);

  if (state && state.url === url) {
    return { content: state.content, error: state.error, loading: false };
  }
  return { content: null, error: false, loading: true };
}

function resultFilename(url: string, fallback: string): string {
  try {
    const path = new URL(url, 'https://example.invalid').pathname;
    const name = path.split('/').filter(Boolean).pop();
    if (name && name.includes('.')) {
      return name;
    }
  } catch {
    // Not a parseable URL; fall through.
  }
  return fallback;
}

function DownloadButton({ url, filename }: { url: string; filename: string }) {
  return (
    <Button asChild variant="outline" size="sm">
      <a href={url} download={filename} target="_blank" rel="noreferrer">
        <Download />
        Baixar
      </a>
    </Button>
  );
}

function Loading() {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      Carregando resultado…
    </div>
  );
}

function TextResult({ url }: { url: string }) {
  const { content, error, loading } = useAsyncText(url);

  if (error) {
    return (
      <StateMessage tone="info" title="Resultado pronto">
        Não foi possível pré-visualizar o conteúdo. Use o botão de download.
      </StateMessage>
    );
  }

  if (loading || content === null) {
    return <Loading />;
  }

  return (
    <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-background/60 p-4 text-sm">
      {content}
    </pre>
  );
}

function JsonResult({ url }: { url: string }) {
  const { content, loading } = useAsyncText(url);

  if (loading || content === null) {
    return (
      <StateMessage tone="info" title="Resultado pronto">
        Baixe o JSON para ver o conteúdo completo.
      </StateMessage>
    );
  }

  let display: string;
  try {
    display = JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    display = content;
  }

  return (
    <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-background/60 p-4 text-sm">
      {display}
    </pre>
  );
}

export function JobResult({ tool, job }: JobResultProps) {
  const url = job.result_url;

  if (job.status === 'error') {
    return (
      <StateMessage tone="error" title="Falha ao processar">
        {job.error ?? 'Erro desconhecido.'}
      </StateMessage>
    );
  }

  if (job.status !== 'done' || !url) {
    return (
      <StateMessage tone="loading" title="Processando…">
        {job.progress > 0 ? `Progresso: ${job.progress}%` : 'Aguardando o worker.'}
      </StateMessage>
    );
  }

  const filename = resultFilename(url, `${tool.slug}-resultado`);
  const isTextual = tool.result === 'text' || tool.result === 'json';

  return (
    <Card className="gap-4">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Resultado</CardTitle>
        {isTextual ? (
          <div className="flex items-center gap-2">
            <DownloadButton url={url} filename={filename} />
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {tool.result === 'text' ? <TextResult url={url} /> : null}
        {tool.result === 'json' ? <JsonResult url={url} /> : null}
        {tool.result === 'audio' ? (
          <audio controls src={url} className="w-full">
            <track kind="captions" />
          </audio>
        ) : null}
        {tool.result === 'image' ? (
          <img src={url} alt="Resultado do processamento" className="max-h-96 rounded-xl" />
        ) : null}
        {tool.result === 'download' ? (
          <div className="flex flex-col gap-3">
            <StateMessage tone="success" title="Resultado pronto">
              Baixe o arquivo processado.
            </StateMessage>
            <DownloadButton url={url} filename={filename} />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
