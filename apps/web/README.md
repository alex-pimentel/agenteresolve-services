# Agenteresolve — Web

Frontend unificado da plataforma de serviços IA: um **catálogo** de 16 ferramentas
(`/`) e uma **rota por ferramenta** (`/{slug}`) dentro do mesmo Service Shell
(`@agenteresolve/ui`).

- **React 19 + TypeScript + Vite + Tailwind v4**
- **Design system** `@agenteresolve/ui` (git dependency) — tokens, `ServiceShell`,
  `Header`, `Footer` e primitivos (Button, Card, Badge, Input, Textarea…)
- **Clerk** opcional: sem publishable key o header degrada com um botão neutro
- **Sem persistência**: entradas e resultados vivem no gateway/R2 `tmp` (TTL 24h)

## Rotas

| Rota         | Conteúdo                                                                 |
| ------------ | ------------------------------------------------------------------------ |
| `/`          | Catálogo agrupado por categoria: No navegador, Texto e LLM, Visão, Áudio |
| `/louder`    | Superfície client-side que aponta para o app Louder standalone           |
| `/translate` | Tradutor funcional (texto → gateway → polling → resultado)               |
| `/{slug}`    | ToolPage genérica para as demais 13 ferramentas (badge **Beta**)         |
| `*`          | Página de ferramenta não encontrada                                      |

Ferramentas marcadas como `beta` já têm UI pronta (entrada → submit → polling →
resultado/download); o gateway responde `501 Not Implemented` até o serviço entrar
no ar, e a UI mostra um aviso claro em vez de quebrar.

## Contrato com o gateway

- `POST {VITE_API_BASE}/api/{slug}/` — JSON `{ text, ...opções }` (texto) ou
  `multipart/form-data` `file + ...opções` (arquivo/imagem/áudio).
  Resposta `202 { task_id, tool, status }`.
- `GET {VITE_API_BASE}/api/{slug}/{task_id}` — `{ task_id, tool, status, progress,
result_url, error }`. `result_url` é um presigned GET quando `status == "done"`.
- `GET /health` → `{ "status": "ok" }`.

O cliente em `src/lib/api.ts` encapsula criação, polling (com timeout/abort) e
leitura de resultado. Nenhum backend real é necessário nos testes (fetch é mockado).

## Ambiente

Copie `.env.example` para `.env` (nunca versione `.env`):

| Variável                     | Padrão                                | Descrição                         |
| ---------------------------- | ------------------------------------- | --------------------------------- |
| `VITE_API_BASE`              | `https://api.agenteresolve.com.br`    | URL do gateway                    |
| `VITE_CLERK_PUBLISHABLE_KEY` | —                                     | opcional; sem ela o login degrada |
| `VITE_LOUDER_URL`            | `https://louder.agenteresolve.com.br` | app Louder standalone             |

## Scripts

```bash
npm ci
npm run dev            # servidor de desenvolvimento
npm run lint           # ESLint
npm run format         # Prettier (write)
npm run format:check   # Prettier (check)
npm run types          # tsc --noEmit
npm test               # Vitest + Testing Library
npm run test:coverage  # cobertura V8 (mínimo 60%)
npm run test:e2e       # Playwright (build + preview)
npm run build          # build de produção (dist/)
```

## Deploy

Cloudflare Pages (`tools.agenteresolve.com.br`). O `public/_redirects` faz o
fallback de SPA (`/* /index.html 200`) para as rotas do React Router.
