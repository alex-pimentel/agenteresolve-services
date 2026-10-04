import { Input, Label, Textarea, cn } from '@agenteresolve/ui';
import { CloudUpload } from 'lucide-react';

import { formatBytes, type ToolConfig } from '../data/tools';

export interface ToolInputProps {
  tool: ToolConfig;
  text: string;
  onTextChange: (value: string) => void;
  file: File | null;
  onFileChange: (file: File | null) => void;
  optionValues: Record<string, string>;
  onOptionChange: (name: string, value: string) => void;
  disabled?: boolean;
}

const FILE_LABEL: Record<string, string> = {
  file: 'Arquivo',
  image: 'Imagem',
  audio: 'Áudio ou vídeo',
};

export function ToolInput({
  tool,
  text,
  onTextChange,
  file,
  onFileChange,
  optionValues,
  onOptionChange,
  disabled = false,
}: ToolInputProps) {
  return (
    <div className="flex flex-col gap-5">
      {tool.input === 'text' ? (
        <div className="flex flex-col gap-2">
          <Label htmlFor="tool-input">Texto</Label>
          <Textarea
            id="tool-input"
            value={text}
            disabled={disabled}
            onChange={(event) => onTextChange(event.target.value)}
            placeholder="Cole ou escreva o texto aqui…"
            className="min-h-48"
          />
          <p className="text-xs text-muted-foreground">
            {text.length.toLocaleString('pt-BR')} caracteres · limite {formatBytes(tool.maxBytes)}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Label htmlFor="tool-input">{FILE_LABEL[tool.input] ?? 'Arquivo'}</Label>
          <label
            htmlFor="tool-input"
            data-testid="file-dropzone"
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface px-4 py-8 text-center transition-colors hover:border-brand/60 hover:bg-surface-strong/60',
              disabled && 'pointer-events-none opacity-50',
            )}
          >
            <CloudUpload className="size-6 text-brand" aria-hidden />
            <span className="text-sm font-medium text-foreground">
              {file ? file.name : 'Clique para selecionar ou arraste o arquivo'}
            </span>
            <span className="text-xs text-muted-foreground">
              {file
                ? `${formatBytes(file.size)} · limite ${formatBytes(tool.maxBytes)}`
                : `Limite ${formatBytes(tool.maxBytes)}`}
            </span>
          </label>
          <input
            id="tool-input"
            type="file"
            accept={tool.accept}
            disabled={disabled}
            className="sr-only"
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          />
        </div>
      )}

      {tool.options?.length ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {tool.options.map((option) => {
            const id = `option-${option.name}`;
            return (
              <div key={option.name} className="flex flex-col gap-2">
                <Label htmlFor={id}>{option.label}</Label>
                {option.type === 'select' ? (
                  <select
                    id={id}
                    value={optionValues[option.name] ?? ''}
                    disabled={disabled}
                    onChange={(event) => onOptionChange(option.name, event.target.value)}
                    className="flex h-9 w-full rounded-lg border border-input bg-surface px-3 py-1 text-sm text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {option.choices?.map((choice) => (
                      <option key={choice.value} value={choice.value}>
                        {choice.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    id={id}
                    value={optionValues[option.name] ?? ''}
                    disabled={disabled}
                    placeholder={option.placeholder}
                    onChange={(event) => onOptionChange(option.name, event.target.value)}
                  />
                )}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
