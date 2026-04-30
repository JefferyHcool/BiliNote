# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BiliNote is an AI video note generation tool. It extracts content from video links (Bilibili, YouTube, Douyin, Kuaishou, local files) and generates structured Markdown notes using LLM models. Full-stack app with a FastAPI backend, React frontend, and optional Tauri desktop packaging.

## Literate Programming

All code written in this project follows Don Knuth's literate programming principles.
The full skill is at `.claude/skills/literate-programming/SKILL.md`.

When creating a new source file or significantly rewriting an existing one, read
`.claude/skills/literate-programming/SKILL.md` and apply it before writing any code.

The five rules in brief:

1. Every file opens with a narrative preamble — why it exists, key design decisions,
   what it deliberately does NOT do
2. Documentation explains reasoning, not signatures — WHY the design is this way,
   not what the function returns
3. Order of presentation follows logical understanding — orchestration before detail,
   concept before mechanism
4. Each file has one clearly stated concern — named in the first sentence of the preamble
5. Inline comments explain WHY, not WHAT — the code already shows what happens

## CUPID Code Review

When reviewing or refactoring code, apply the CUPID lens documented at
`.claude/skills/cupid-code-review/SKILL.md`.

The five properties in brief:

1. **Composable** — can it be used independently without hidden dependencies?
2. **Unix philosophy** — does it do one thing completely and well?
3. **Predictable** — does it behave as its name suggests, with no hidden side effects?
4. **Idiomatic** — does it follow the grain of the language and project conventions?
5. **Domain-based** — do its names come from the problem domain, not the technical implementation?

## Workflow

### Spec-First Change Discipline

Any change to application behaviour must flow through the spec before touching
implementation code:

1. Update the spec — add or revise user stories, acceptance scenarios, and FRs
2. Update the implementation plan — reflect new or changed FRs
3. Write failing tests from the spec — confirm red before writing implementation
4. Update the implementation — until failing tests turn green
5. Refactor — clean up while keeping all tests green

### Test-Driven Development

Follow red-green-refactor strictly:

1. RED — write a failing test that describes the desired behaviour
2. GREEN — write the minimal production code needed to make the test pass
3. REFACTOR — clean up while keeping all tests green

No production code without a failing test first.

### Branch Discipline

Never commit directly to `main`. At the start of any task:

1. Create a GitHub issue describing the task
2. Create a branch: `git checkout -b <short-descriptive-name>`
   (lowercase, hyphen-separated, e.g. `add-search`, `fix-renderer-wrapping`)

### Commit Messages

Write concise commit messages that describe what changed and why. No postamble,
no attribution lines. The message ends when the description ends.

### CHANGELOG

Before every PR, update CHANGELOG.md:

- Add a dated section at the top if today's date is not already present
- Group entries under a short theme heading
- One bullet per change: what changed and why it matters

### PR Health Check

After every push and PR creation:

1. Run `gh pr checks <number> --watch`
2. If any check fails, fetch the log: `gh run view <run-id> --log-failed`
3. Fix every error, then commit (never amend) and push
4. Repeat until all checks are green

## Build and Test

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

### Test
```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend lint
cd BillNote_frontend && pnpm lint
```

### Lint & Format
```bash
# Backend — no configured linter; use ruff or black as needed
# Frontend
cd BillNote_frontend && pnpm lint
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

## Learnings

REFLECTION_LOG.md contains past session learnings — surprises,
failures, and improvement proposals. Agents should read recent
entries before starting work to avoid repeating past mistakes.

## Project Constraints

- B站下载需要有效的 cookies.txt 文件，路径通过环境变量 `BILIBILI_COOKIES_FILE` 配置
- 不使用硬编码绝对路径，所有路径通过 `path_helper` 工具函数获取
- cookies.txt 等敏感文件不提交到 git（已在 .gitignore 中配置）
- 视频理解功能必须使用多模态模型（如 doubao-seed-2.0-pro），且截图数量受 MAX_GRIDS=25 上限约束
- 前端 pnpm 管理依赖，不使用 npm/yarn

## Obsidian 同步规则

> 以下规则在每次会话中自动生效，无需重复提醒。

**Vault 根路径：** `D:\iori\obsidian-vault`  
**本项目文档目录：** `01-Projects\BiliNote\`

### 工作日志（每个任务节点后自动写入）

**触发时机：** 每完成一个明确的任务节点  
**文件路径：** `01-Projects\BiliNote\工作日志\{{YYYY-MM-DD}}.md`  
**写入方式：** 追加，不覆盖当天已有内容  
**文件不存在时：** 自动创建，顶部写入 `# {{YYYY-MM-DD}} 工作日志`

**日志格式：**

```markdown
## {{HH:MM}} {{任务标题}}

**完成内容：**
- 具体做了什么

**涉及文件：**
- `路径/文件名` — 变更说明

**决策与备注：**
- 为什么这样做、遇到的问题、解决思路
```

### 架构决策记录（ADR）

**触发时机：** 做出影响架构/技术方向的决策时  
**文件路径：** `01-Projects\BiliNote\决策记录\{{YYYY-MM-DD}}-{{决策标题}}.md`  
**写入方式：** 新建文件

**ADR 格式：**

```markdown
# ADR-{{编号}}：{{决策标题}}

**日期：** {{YYYY-MM-DD}}  
**状态：** 已采纳

## 背景
为什么需要做这个决策

## 决策
选择了什么方案

## 原因
为什么选这个而不是其他方案

## 后果
这个决策带来的影响（正面/负面）
```

### 功能说明文档

**触发时机：** 新功能开发完成时  
**文件路径：** `01-Projects\BiliNote\功能说明.md`  
**写入方式：** 在对应章节追加，保持文档结构完整

### 快速指令

在会话中直接说以下关键词即可触发对应操作：

| 关键词            | 动作                                   |
| ----------------- | -------------------------------------- |
| `写日志`          | 把当前会话内容整理写入今日工作日志     |
| `记录决策 [标题]` | 新建一条 ADR 决策记录                  |
| `更新功能文档`    | 把刚完成的功能追加到功能说明           |
| `同步到vault`     | 把当前会话所有重要内容一次性写入 Vault |
