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

## Architecture

**Backend** (`backend/`) — FastAPI app, entry point `main.py`:
- `app/routers/` — API routes: `note.py` (generation), `provider.py`, `model.py`, `config.py`
- `app/services/` — Business logic: `note.py` (NoteGenerator orchestrates the full pipeline), `task_serial_executor.py` (task queue)
- `app/downloaders/` — Platform adapters (bilibili, youtube, douyin, kuaishou, local) with shared `base.py` interface
- `app/transcriber/` — Speech-to-text engines (fast-whisper, groq, bcut, kuaishou, mlx-whisper) with factory in `transcriber_provider.py`
- `app/gpt/` — LLM integration with factory pattern (`gpt_factory.py`), prompt templates (`prompt.py`, `prompt_builder.py`), and `request_chunker.py` for long transcripts
- `app/db/` — SQLite + SQLAlchemy: DAO pattern (`provider_dao.py`, `model_dao.py`, `video_task_dao.py`), models in `models/`
- `app/utils/` — `response.py` (ResponseWrapper for consistent JSON), `video_helper.py` (screenshots via FFmpeg), `export.py` (PDF/DOCX)
- `events/` (root level) — Blinker signal system for post-processing (e.g., temp file cleanup after transcription)

**Frontend** (`BillNote_frontend/src/`) — React 19 + Vite + Tailwind + shadcn/ui:
- `pages/HomePage/` — Main note generation UI: `NoteForm.tsx` (input), `MarkdownViewer.tsx` (preview), `MarkmapComponent.tsx` (mind map)
- `pages/SettingPage/` — LLM provider management, system monitoring, transcriber config
- `store/` — Zustand stores: `taskStore`, `modelStore`, `configStore`, `providerStore`
- `services/` — Axios API clients matching backend routes
- `hooks/useTaskPolling.ts` — Polls task status every 3 seconds
- `components/ui/` — shadcn/ui (Radix-based) components
- Path alias: `@` → `./src`

**Core Workflow**: User submits URL → task queued → download video → extract audio (FFmpeg) → transcribe (Whisper/Groq/etc) → generate notes (LLM) → frontend polls for completion → display Markdown + mind map.

## Key Configuration

- **Ports**: Backend 8483, Frontend dev 3015, Docker maps 3015→80
- **Environment**: Root `.env` (copy from `.env.example`). LLM API keys are configured through the UI, not env vars.
- **Database**: SQLite at `backend/app/db/bili_note.db`, auto-initialized on first run
- **FFmpeg**: Required system dependency for video/audio processing
- **Vite proxy**: Dev server proxies `/api` and `/static` to backend (configured in `vite.config.ts`, reads env from parent dir)

## Code Style

- **Frontend**: ESLint + Prettier (2 spaces, single quotes, 100 char width, Tailwind plugin). TypeScript strict mode.
- **Backend**: Python with type hints. No configured linter. Uses Pydantic models for validation.
- **Note**: The frontend directory is named `BillNote_frontend` (not "Bili").
