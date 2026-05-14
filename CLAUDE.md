# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BiliNote is an AI video note generation tool. It extracts content from video links (Bilibili, YouTube, Douyin, Kuaishou, local files) and generates structured Markdown notes using LLM models. Full-stack app with a FastAPI backend, React frontend, and optional Tauri desktop packaging.

## Development Commands

### Backend (Python 3.11 + FastAPI)
```bash
cd backend
pip install -r requirements.txt
python main.py                    # Starts on 0.0.0.0:8483
pytest                            # Run tests in backend/tests/
pytest tests/test_request_chunker.py::test_name   # Run a single test
```

### Frontend (React 19 + Vite + TypeScript)
```bash
cd BillNote_frontend
pnpm install
pnpm dev          # Dev server on port 3015, proxies /api to backend
pnpm build        # Production build
pnpm lint         # ESLint
```

### Docker
```bash
docker-compose up                              # Web stack (backend + frontend + nginx)
docker-compose -f docker-compose.gpu.yml up    # GPU variant
```

### Desktop (Tauri)
```bash
cd backend && ./build.sh          # Build PyInstaller backend binary
cd BillNote_frontend && pnpm tauri build
```

### Browser Extension (Vue 3 + vitesse-webext, MV3)
```bash
cd BillNote_extension
pnpm install
pnpm dev          # watch mode → ./extension/
pnpm build        # production build → ./extension/
pnpm typecheck
pnpm test         # Vitest unit tests
pnpm test:e2e     # Playwright e2e
```
Load unpacked at `chrome://extensions/` → select `BillNote_extension/extension/`. Talks to the same backend at `http://localhost:8483` (configurable in the options page). CORS in `backend/main.py` already accepts `chrome-extension://` and `moz-extension://` via regex.

## Architecture

**Backend** (`backend/`) — FastAPI app, entry point `main.py`:
- `app/routers/` — API routes: `note.py` (generation), `provider.py`, `model.py`, `config.py`, `chat.py` (RAG Q&A on generated notes)
- `app/services/` — Business logic:
  - `note.py` — `NoteGenerator` orchestrates the full pipeline (download → transcribe → LLM → notes)
  - `task_serial_executor.py` — task queue
  - `chat_service.py` + `chat_tools.py` + `vector_store.py` — RAG-based AI Q&A with Function Calling, indexing transcripts and video metadata
  - `cookie_manager.py` — per-platform cookie storage; injected into yt-dlp by downloaders (e.g. Bilibili)
  - `transcriber_config_manager.py` — persisted transcriber settings
- `app/downloaders/` — Platform adapters (bilibili, youtube, douyin, kuaishou, local) with shared `base.py` interface
- `app/transcriber/` — Speech-to-text engines (fast-whisper, groq, bcut, kuaishou, mlx-whisper) with factory in `transcriber_provider.py`. YouTube path prefers existing subtitles and skips audio download when available.
- `app/gpt/` — LLM integration with factory pattern (`gpt_factory.py`), prompt templates (`prompt.py`, `prompt_builder.py`), and `request_chunker.py` for long transcripts
- `app/db/` — SQLite + SQLAlchemy: DAO pattern (`provider_dao.py`, `model_dao.py`, `video_task_dao.py`), models in `models/`
- `app/utils/` — `response.py` (ResponseWrapper for consistent JSON), `video_helper.py` (screenshots via FFmpeg), `export.py` (PDF/DOCX), `ppt_generator.py`, `minio_client.py`
- `app/validators/video_url_validator.py` — URL → platform detection (mirrored client-side in the extension)
- `app/exceptions/` — `BizException` + handlers wired in `main.py` via `register_exception_handlers`
- `backend/events/` — Blinker signal system for post-processing (e.g., temp file cleanup after transcription); registered in `lifespan` startup
- `backend/ffmpeg_helper.py` — `ensure_ffmpeg_or_raise` is called at startup; respects `FFMPEG_BIN_PATH`

**Frontend** (`BillNote_frontend/src/`) — React 19 + Vite + Tailwind + shadcn/ui:
- `pages/HomePage/` — Main note generation UI: `NoteForm.tsx` (input), `MarkdownViewer.tsx` (preview), `MarkmapComponent.tsx` (mind map)
- `pages/SettingPage/` — LLM provider management, system monitoring, transcriber config
- `store/` — Zustand stores: `taskStore`, `modelStore`, `configStore`, `providerStore`. Persists to IndexedDB.
- `services/` — Axios API clients matching backend routes
- `hooks/useTaskPolling.ts` — Polls task status every 3 seconds
- `components/ui/` — shadcn/ui (Radix-based) components
- `i18n/` — `react-i18next` setup with locale JSON in `i18n/locales/`; toggled via `components/LanguageSwitcher.tsx`
- Path alias: `@` → `./src`

**Core Workflow**: User submits URL → task queued → download video → extract audio (FFmpeg) → transcribe (Whisper/Groq/etc) → generate notes (LLM) → frontend polls for completion → display Markdown + mind map.

**Browser Extension** (`BillNote_extension/`) — Vue 3 + Vite + UnoCSS + webextension-polyfill, MV3:
- `src/popup/Popup.vue` — main entry: detects platform from active tab URL, drives generate flow, shows progress + markdown
- `src/options/Options.vue` — settings: backend URL, default provider/model (loaded from `/get_all_providers` + `/get_models_by_provider/{id}`), quality, screenshot/link toggles, style
- `src/logic/api.ts` — backend API client (uses `settings.backendUrl`, unwraps `ResponseWrapper`, absolutizes `/static/screenshots/...` image paths)
- `src/logic/storage.ts` — `chrome.storage.local`-backed Pinia-like state via `useWebExtensionStorage` for settings + last 30 tasks
- `src/logic/platform.ts` — URL → platform detection mirroring `backend/app/validators/video_url_validator.py`
- `src/sidepanel/`, `src/contentScripts/` — placeholders for P2/P3 (floating button, side panel mind map, RAG chat); not wired into MVP UX
- `src/manifest.ts` — MV3 manifest, popup is default action; `host_permissions: *://*/*`
- Polling lives client-side in popup (3 s interval while open); MV3 service worker is intentionally thin in P1

## Key Configuration

- **Ports**: Backend 8483, Frontend dev 3015, Docker maps 3015→80
- **Environment**: Root `.env` (copy from `.env.example`). LLM API keys are configured through the UI, not env vars.
- **Database**: SQLite at `backend/app/db/bili_note.db`, auto-initialized on first run
- **FFmpeg**: Required system dependency for video/audio processing
- **Vite proxy**: Dev server proxies `/api` and `/static` to backend (configured in `vite.config.ts`, reads env from parent dir; falls back to current dir when `DOCKER_BUILD` is set)
- **CORS**: `backend/main.py` uses a regex (`CORS_ORIGIN_REGEX`) that allows localhost, `tauri.localhost`, and `chrome-extension://` / `moz-extension://` origins — required for the desktop app and the browser extension.

## Code Style

- **Frontend**: ESLint + Prettier (2 spaces, single quotes, 100 char width, Tailwind plugin). TypeScript strict mode.
- **Backend**: Python with type hints. No configured linter. Uses Pydantic models for validation.
- **Note**: The frontend directory is named `BillNote_frontend` (not "Bili").
