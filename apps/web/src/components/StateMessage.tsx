import type { ReactNode } from 'react';
import { cn } from '@agenteresolve/ui';
import { AlertCircle, CheckCircle2, Info, Loader2 } from 'lucide-react';

export type StateTone = 'info' | 'error' | 'success' | 'loading';

const TONE_STYLES: Record<StateTone, { wrapper: string; icon: string }> = {
  info: { wrapper: 'border-border bg-surface text-foreground', icon: 'text-brand-cyan' },
  error: {
    wrapper: 'border-destructive/50 bg-destructive/10 text-foreground',
    icon: 'text-destructive',
  },
  success: {
    wrapper: 'border-success/50 bg-success/10 text-foreground',
    icon: 'text-success',
  },
  loading: { wrapper: 'border-border bg-surface text-foreground', icon: 'text-brand' },
};

export interface StateMessageProps {
  tone: StateTone;
  title: string;
  children?: ReactNode;
  className?: string;
}

function ToneIcon({ tone }: { tone: StateTone }) {
  if (tone === 'error') {
    return <AlertCircle className="size-4" aria-hidden />;
  }
  if (tone === 'success') {
    return <CheckCircle2 className="size-4" aria-hidden />;
  }
  if (tone === 'loading') {
    return <Loader2 className="size-4 animate-spin" aria-hidden />;
  }
  return <Info className="size-4" aria-hidden />;
}

export function StateMessage({ tone, title, children, className }: StateMessageProps) {
  const styles = TONE_STYLES[tone];
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-3 rounded-xl border px-4 py-3 text-sm',
        styles.wrapper,
        className,
      )}
    >
      <span className={cn('mt-0.5', styles.icon)}>
        <ToneIcon tone={tone} />
      </span>
      <div className="flex flex-col gap-1">
        <span className="font-medium">{title}</span>
        {children ? <span className="text-muted-foreground">{children}</span> : null}
      </div>
    </div>
  );
}
