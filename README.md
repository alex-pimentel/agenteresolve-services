# Agenteresolve AI Services

[![CI](https://github.com/alex-pimentel/agenteresolve-services/actions/workflows/ci.yml/badge.svg)](https://github.com/alex-pimentel/agenteresolve-services/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/alex-pimentel/agenteresolve-services)](https://github.com/alex-pimentel/agenteresolve-services/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Unified AI services platform: a single **FastAPI gateway**, one **Celery worker image** with
`text` / `vision` / `audio` queues, and a shared **`common`** package holding the job model,
object storage and provider abstraction.

Everything external is reached by **URL + key** (Redis, Postgres, Cloudflare R2, LLM,
embeddings, OCR, vision, audio, TTS), so moving a component to another VPS only means
changing env. No user content is persisted: inputs/results live in R2 `tmp` (24h lifecycle)
and in ephemeral job state.

## Layout

```
services/
├── apps/
│   ├── gateway/          # FastAPI: /health, POST/GET /api/{slug}/
│   └── worker/           # Celery app, task routing, tool handlers
├── packages/
│   └── common/           # job model, catalog, R2 + job stores, providers
├── Dockerfile            # gateway image
├── Dockerfile.worker     # worker image
├── docker-compose.coolify.yml
├── .env.example
└── pyproject.toml        # uv workspace + ruff/mypy/pytest config
```

## Tool catalogue (16 slugs)

| Queue | Slugs | State |
|---|---|---|
| client-side | `louder` | browser only; gateway returns 501 |
| `text` | `docuextract`, `askyourdocs`, `datachat`, `feedback`, `seo`, **`translate`**, `contracts` | `translate` implemented, rest 501 |
| `vision` | `ocr`, `anonymize`, `alttext`, `objectcount` | 501 stubs |
| `audio` | `transcribe`, `tts`, `audio-enhance`, `voicechat` | 501 stubs |

The registry lives in `packages/common/common/catalog.py`. Every slug not implemented is
registered and answered with `501 Not Implemented` and a clear message.

## API

- `GET /health` → `{"status": "ok"}`
- `POST /api/{slug}/` — JSON (`{"text", "target", "tone"}`) or `multipart/form-data`
  (`file` or `text`). Returns `202 {"task_id", "tool", "status"}`.
- `GET /api/{slug}/{task_id}` — the job model
  `{task_id, tool, status, progress, result_url, error}`; `result_url` is a short-lived
  presigned GET when `status == "done"`.

Clerk JWT verification is an optional dependency: when `CLERK_JWKS_URL` is set and an
`Authorization: Bearer <token>` header is sent, it is verified via JWKS. Anonymous requests
are always allowed.

## Providers (portability)

`packages/common/common/providers/` defines one protocol per capability. The factory picks
a backend from env:

| Capability | Env | Selection |
|---|---|---|
| LLM | `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | remote if URL or key set; **default OpenRouter** |
| Embeddings | `EMBEDDINGS_BASE_URL` / `EMBEDDINGS_API_KEY` / `EMBEDDINGS_MODEL` | remote if URL set, else local |
| OCR | `OCR_URL` / `OCR_KEY` | remote if URL set, else local |
| Vision | `VISION_URL` / `VISION_KEY` | remote if URL set, else local |
| Audio | `AUDIO_URL` / `AUDIO_KEY` | remote if URL set, else local |
| TTS | `TTS_URL` / `TTS_KEY` | remote if URL set, else local |

Only the LLM path is exercised end-to-end (by `translate`); the other capabilities expose
their contracts and raise `ProviderUnavailable` until a backend is configured. Workers load
heavy models lazily on first use (idle unload is a worker lifecycle concern; heavy queues run
`--concurrency=1`).

## Local development

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is provisioned from `.python-version`).

```bash
uv sync --all-packages          # create .venv with all workspace deps
cp .env.example .env            # optional; in-memory stores are used when unset
uv run pytest                   # test suite (no network)
uv run ruff check .             # lint
uv run ruff format --check .    # format
uv run mypy                     # types
```

Run the gateway:

```bash
uv run uvicorn gateway.main:app --reload --port 8000
```

Run a worker (needs `REDIS_URL`; without it, in-memory stores are single-process only):

```bash
uv run celery -A worker.celery_app:celery_app worker -Q text --concurrency=1
```

## Tests

The reference flow (`translate`) is covered end-to-end with a `FakeLLM` and in-memory
stores — **no network is used**:

- `common`: job model, catalogue, stores, provider factory.
- `worker`: `translate` handler and the `process_job` pipeline (success + error paths).
- `gateway`: health, unknown slug (404), stub (501), full JSON and multipart job flow,
  missing task (404).

## Docker / Coolify

```bash
docker compose -f docker-compose.coolify.yml up --build
```

The compose file defines `gateway` + `worker-text` + `worker-vision` + `worker-audio`
(`--concurrency=1`). Redis/Postgres/R2/inference are **not** defined here — supply
`REDIS_URL` and the rest via env (Coolify secrets). A `model-cache` volume keeps downloaded
models between restarts.

## Frontend (`apps/web`)

The unified React frontend lives in `apps/web`. It consumes the shared design system via the
git dependency `@agenteresolve/ui` (`github:alex-pimentel/agenteresolve-ui#v0.1.0`), which is
built on install by the package's `prepare` script.

```bash
cd apps/web
npm ci
npm run build        # static output in apps/web/dist
```

### Deploy (Cloudflare Pages)

```bash
npx wrangler pages deploy apps/web/dist --project-name=agenteresolve-services
```

Set `VITE_CLERK_PUBLISHABLE_KEY` (optional) in the Pages project for the shared login.

## Environment

See [`.env.example`](.env.example) for the full, documented list (Redis, R2, Clerk, all
provider endpoints, worker settings).
