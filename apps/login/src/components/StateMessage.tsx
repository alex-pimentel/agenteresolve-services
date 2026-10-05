import * as React from 'react';
import { cn } from '@agenteresolve/ui';

export function StateMessage({
  tone,
  title,
  children,
  className,
}: {
  tone: 'info' | 'error';
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'rounded-xl border p-4 text-sm',
        tone === 'error'
          ? 'border-red-500/30 bg-red-500/10 text-red-200'
          : 'border-brand-500/30 bg-brand-500/10 text-muted-foreground',
        className,
      )}
    >
      <p className="font-semibold text-white">{title}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}
