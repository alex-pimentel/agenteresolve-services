import {
  Accessibility,
  AudioLines,
  Boxes,
  EyeOff,
  FileJson,
  Languages,
  Mic,
  MicVocal,
  MessageSquare,
  MessagesSquare,
  Scale,
  ScanText,
  Search,
  Table,
  Volume2,
  Waves,
  type LucideIcon,
} from 'lucide-react';

export type ToolCategory = 'client' | 'text' | 'vision' | 'audio';

/** How the user provides input to a tool. */
export type InputKind = 'text' | 'file' | 'image' | 'audio';

/** How a successful result is rendered. */
export type ResultKind = 'text' | 'json' | 'download' | 'audio' | 'image';

export type OptionType = 'select' | 'text';

export interface ToolOption {
  name: string;
  label: string;
  type: OptionType;
  defaultValue?: string;
  placeholder?: string;
  choices?: { value: string; label: string }[];
}

export interface ToolConfig {
  slug: string;
  name: string;
  description: string;
  category: ToolCategory;
  input: InputKind;
  /** `accept` attribute for the file input. */
  accept?: string;
  /** Maximum input size in bytes (mirrors the gateway catalogue). */
  maxBytes: number;
  /** `true` only for tools wired end-to-end at the gateway. */
  implemented: boolean;
  /** `true` for registered-but-stubbed tools (shows a beta badge). */
  beta: boolean;
  result: ResultKind;
  icon: LucideIcon;
  options?: ToolOption[];
  /** `client` tools run in the browser and have no gateway endpoint. */
  route: 'gateway' | 'client';
  note?: string;
}

export interface CategoryMeta {
  id: ToolCategory;
  title: string;
  description: string;
}

const MB = 1024 * 1024;
const KB = 1024;

export const TRANSLATE_LANGUAGES: { value: string; label: string }[] = [
  { value: 'en', label: 'Inglês' },
  { value: 'pt', label: 'Português' },
  { value: 'es', label: 'Espanhol' },
  { value: 'fr', label: 'Francês' },
  { value: 'de', label: 'Alemão' },
  { value: 'it', label: 'Italiano' },
  { value: 'nl', label: 'Holandês' },
  { value: 'pl', label: 'Polonês' },
  { value: 'sv', label: 'Sueco' },
  { value: 'tr', label: 'Turco' },
  { value: 'ru', label: 'Russo' },
  { value: 'ar', label: 'Árabe' },
  { value: 'hi', label: 'Hindi' },
  { value: 'ja', label: 'Japonês' },
  { value: 'ko', label: 'Coreano' },
  { value: 'zh', label: 'Chinês' },
];

const TONE_CHOICES = [
  { value: 'neutral', label: 'Neutro' },
  { value: 'formal', label: 'Formal' },
  { value: 'casual', label: 'Casual' },
];

const LANG_CHOICES = [
  { value: 'pt', label: 'Português' },
  { value: 'en', label: 'Inglês' },
  { value: 'es', label: 'Espanhol' },
];

export const CATEGORIES: CategoryMeta[] = [
  {
    id: 'client',
    title: 'No navegador',
    description: 'Ferramentas que rodam 100% no seu dispositivo, sem upload.',
  },
  {
    id: 'text',
    title: 'Texto e LLM',
    description: 'Tradução, extração, classificação e geração de conteúdo.',
  },
  {
    id: 'vision',
    title: 'Visão',
    description: 'OCR, anonimização, legendas e contagem em imagens.',
  },
  {
    id: 'audio',
    title: 'Áudio',
    description: 'Transcrição, síntese de voz e realce de áudio.',
  },
];

export const TOOLS: ToolConfig[] = [
  {
    slug: 'louder',
    name: 'Louder',
    description: 'Leia PDFs e textos em voz alta, 100% no navegador, sem upload.',
    category: 'client',
    input: 'file',
    accept: '.pdf,.txt,.md,text/plain,application/pdf',
    maxBytes: 25 * MB,
    implemented: true,
    beta: false,
    result: 'text',
    icon: Volume2,
    route: 'client',
    note: 'Ferramenta client-side: abre o app Louder standalone. Nada sai do seu dispositivo.',
  },
  {
    slug: 'docuextract',
    name: 'DocuExtract',
    description: 'Extrai dados estruturados (JSON) de faturas, contratos e recibos.',
    category: 'text',
    input: 'file',
    accept: '.pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/*',
    maxBytes: 20 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: FileJson,
    route: 'gateway',
    options: [
      {
        name: 'schema',
        label: 'Schema',
        type: 'select',
        defaultValue: 'auto',
        choices: [
          { value: 'auto', label: 'Automático' },
          { value: 'invoice', label: 'Fatura' },
          { value: 'contract', label: 'Contrato' },
          { value: 'receipt', label: 'Recibo' },
        ],
      },
    ],
  },
  {
    slug: 'askyourdocs',
    name: 'AskYourDocs',
    description: 'Perguntas sobre seus documentos com citações (RAG efêmero).',
    category: 'text',
    input: 'file',
    accept: '.pdf,.txt,.md,application/pdf,text/plain',
    maxBytes: 20 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: MessagesSquare,
    route: 'gateway',
  },
  {
    slug: 'datachat',
    name: 'DataChat',
    description: 'Perguntas em linguagem natural sobre planilhas CSV/XLSX.',
    category: 'text',
    input: 'file',
    accept: '.csv,.xlsx,.xls,text/csv',
    maxBytes: 20 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: Table,
    route: 'gateway',
  },
  {
    slug: 'feedback',
    name: 'FeedbackClassifier',
    description: 'Classifica avaliações por sentimento, tema e urgência.',
    category: 'text',
    input: 'text',
    maxBytes: 200 * KB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: MessageSquare,
    route: 'gateway',
  },
  {
    slug: 'seo',
    name: 'SEOContent',
    description: 'Gera títulos, meta, outline e posts sociais otimizados.',
    category: 'text',
    input: 'text',
    maxBytes: 200 * KB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: Search,
    route: 'gateway',
    options: [
      { name: 'lang', label: 'Idioma', type: 'select', defaultValue: 'pt', choices: LANG_CHOICES },
      {
        name: 'tone',
        label: 'Tom',
        type: 'select',
        defaultValue: 'neutral',
        choices: TONE_CHOICES,
      },
      { name: 'keyword', label: 'Palavra-chave', type: 'text', placeholder: 'ex.: energia solar' },
    ],
  },
  {
    slug: 'translate',
    name: 'Translator',
    description: 'Traduz textos preservando markdown e formatação.',
    category: 'text',
    input: 'text',
    maxBytes: 10 * MB,
    implemented: true,
    beta: false,
    result: 'text',
    icon: Languages,
    route: 'gateway',
    options: [
      {
        name: 'target',
        label: 'Idioma de destino',
        type: 'select',
        defaultValue: 'en',
        choices: TRANSLATE_LANGUAGES,
      },
      {
        name: 'tone',
        label: 'Tom',
        type: 'select',
        defaultValue: 'neutral',
        choices: TONE_CHOICES,
      },
    ],
  },
  {
    slug: 'contracts',
    name: 'ContractChecker',
    description: 'Aponta riscos, cláusulas relevantes e obrigações em contratos.',
    category: 'text',
    input: 'file',
    accept: '.pdf,.docx,.txt,application/pdf,text/plain',
    maxBytes: 20 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: Scale,
    route: 'gateway',
    note: 'Apoio à decisão. Não é aconselhamento jurídico.',
  },
  {
    slug: 'ocr',
    name: 'OcrExtract',
    description: 'Extrai texto e blocos com coordenadas de imagens e PDFs.',
    category: 'vision',
    input: 'image',
    accept: 'image/png,image/jpeg,image/webp,.pdf,application/pdf',
    maxBytes: 20 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: ScanText,
    route: 'gateway',
    options: [{ name: 'lang', label: 'Idioma', type: 'text', placeholder: 'ex.: por+eng' }],
  },
  {
    slug: 'anonymize',
    name: 'Anonymize',
    description: 'Desfoca rostos, placas e PII em imagens.',
    category: 'vision',
    input: 'image',
    accept: 'image/png,image/jpeg,image/webp',
    maxBytes: 10 * MB,
    implemented: true,
    beta: false,
    result: 'image',
    icon: EyeOff,
    route: 'gateway',
    options: [
      {
        name: 'mode',
        label: 'Modo',
        type: 'select',
        defaultValue: 'blur',
        choices: [
          { value: 'blur', label: 'Desfocar' },
          { value: 'pixelate', label: 'Pixelar' },
          { value: 'black', label: 'Tarjar (preto)' },
        ],
      },
      { name: 'categories', label: 'Categorias', type: 'text', placeholder: 'faces, plates, text' },
    ],
  },
  {
    slug: 'alttext',
    name: 'AltText',
    description: 'Gera alt-text e legendas acessíveis para imagens.',
    category: 'vision',
    input: 'image',
    accept: 'image/png,image/jpeg,image/webp',
    maxBytes: 10 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: Accessibility,
    route: 'gateway',
    options: [
      { name: 'lang', label: 'Idioma', type: 'select', defaultValue: 'pt', choices: LANG_CHOICES },
      {
        name: 'style',
        label: 'Estilo',
        type: 'select',
        defaultValue: 'accessible',
        choices: [
          { value: 'accessible', label: 'Acessível' },
          { value: 'seo', label: 'SEO' },
          { value: 'literal', label: 'Literal' },
        ],
      },
    ],
  },
  {
    slug: 'objectcount',
    name: 'ObjectCount',
    description: 'Detecta e conta objetos por classe em imagens.',
    category: 'vision',
    input: 'image',
    accept: 'image/png,image/jpeg,image/webp',
    maxBytes: 10 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: Boxes,
    route: 'gateway',
    options: [
      { name: 'classes', label: 'Classes', type: 'text', placeholder: 'ex.: person, car' },
      { name: 'min_score', label: 'Score mínimo', type: 'text', placeholder: 'ex.: 0.5' },
    ],
  },
  {
    slug: 'transcribe',
    name: 'Transcribe',
    description: 'Transcreve áudio/vídeo com timestamps e resumo opcional.',
    category: 'audio',
    input: 'audio',
    accept: 'audio/*,video/*',
    maxBytes: 25 * MB,
    implemented: true,
    beta: false,
    result: 'json',
    icon: Mic,
    route: 'gateway',
    options: [
      {
        name: 'lang',
        label: 'Idioma',
        type: 'select',
        defaultValue: 'auto',
        choices: [
          { value: 'auto', label: 'Detectar' },
          { value: 'pt', label: 'Português' },
          { value: 'en', label: 'Inglês' },
        ],
      },
      {
        name: 'summarize',
        label: 'Resumir',
        type: 'select',
        defaultValue: 'false',
        choices: [
          { value: 'false', label: 'Não' },
          { value: 'true', label: 'Sim' },
        ],
      },
    ],
  },
  {
    slug: 'tts',
    name: 'Tts',
    description: 'Converte texto em narração com vozes neurais (Piper).',
    category: 'audio',
    input: 'text',
    maxBytes: 100 * KB,
    implemented: true,
    beta: false,
    result: 'audio',
    icon: AudioLines,
    route: 'gateway',
    options: [
      { name: 'voice', label: 'Voz', type: 'text', placeholder: 'ex.: pt_BR-faber-medium' },
      { name: 'lang', label: 'Idioma', type: 'select', defaultValue: 'pt', choices: LANG_CHOICES },
      {
        name: 'speed',
        label: 'Velocidade',
        type: 'select',
        defaultValue: '1',
        choices: [
          { value: '0.75', label: '0,75x' },
          { value: '1', label: '1x' },
          { value: '1.25', label: '1,25x' },
          { value: '1.5', label: '1,5x' },
        ],
      },
    ],
  },
  {
    slug: 'audio-enhance',
    name: 'AudioEnhance',
    description: 'Reduz ruído, isola a voz e normaliza o áudio.',
    category: 'audio',
    input: 'audio',
    accept: 'audio/*,video/*',
    maxBytes: 25 * MB,
    implemented: true,
    beta: false,
    result: 'audio',
    icon: Waves,
    route: 'gateway',
    options: [
      {
        name: 'mode',
        label: 'Modo',
        type: 'select',
        defaultValue: 'denoise',
        choices: [
          { value: 'denoise', label: 'Reduzir ruído' },
          { value: 'voice-isolate', label: 'Isolar voz' },
          { value: 'normalize', label: 'Normalizar' },
        ],
      },
    ],
  },
  {
    slug: 'voicechat',
    name: 'VoiceChat',
    description: 'Conversa por voz com IA (STT + LLM + TTS) em uma sessão.',
    category: 'audio',
    input: 'audio',
    accept: 'audio/*',
    maxBytes: 25 * MB,
    implemented: true,
    beta: false,
    result: 'audio',
    icon: MicVocal,
    route: 'gateway',
    options: [
      { name: 'persona', label: 'Persona', type: 'text', placeholder: 'ex.: assistente útil' },
      { name: 'lang', label: 'Idioma', type: 'select', defaultValue: 'pt', choices: LANG_CHOICES },
    ],
  },
];

export const TOOL_SLUGS: string[] = TOOLS.map((tool) => tool.slug);

export function getTool(slug: string): ToolConfig | undefined {
  return TOOLS.find((tool) => tool.slug === slug);
}

export function toolsByCategory(category: ToolCategory): ToolConfig[] {
  return TOOLS.filter((tool) => tool.category === category);
}

export function formatBytes(bytes: number): string {
  if (bytes >= MB) {
    const value = bytes / MB;
    return `${Number.isInteger(value) ? value : value.toFixed(1)} MB`;
  }
  return `${Math.round(bytes / KB)} KB`;
}
