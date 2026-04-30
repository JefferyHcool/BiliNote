# Compound Learning

This file is the project's persistent memory across AI sessions.
It accumulates patterns, gotchas, and decisions so that each session
builds on what previous sessions learned — rather than rediscovering
the same things from scratch.

IMPORTANT: This file is often generated or updated by LLM agents.
Review new entries with the same scepticism you would apply to any
generated content. Entries should reflect observed reality in the
codebase, not aspirational conventions.

## STYLE

- Prefer `get_logger(__name__)` from `app.utils.logger` over `logging.getLogger(__name__)` in backend — the project logger auto-logs to both console and file
- Backend downloaders follow the ABC `Downloader` base class in `base.py` — always check the interface before adding a new platform adapter
- Frontend form components use `react-hook-form` + `zod` resolver pattern — study `NoteForm.tsx` before adding new forms
- Use `@` path alias for frontend imports (maps to `./src`)
- API responses use `ResponseWrapper` envelope format from `app.utils.response`

## GOTCHAS

- B站下载 HTTP 412 错误：通常由过时的 yt-dlp 或缺少 cookies 引起。升级 yt-dlp 到最新版，确保 cookies.txt 在正确位置
- cookies.txt 查找路径优先级：环境变量 `BILIBILI_COOKIES_FILE` → backend 根目录 → 当前工作目录 → `/app/`（Docker）
- 截图功能不生效的三层陷阱：
  1. `need_full_download` 仅检查 `screenshot` 布尔字段，需同时检查 `"screenshot" in _format`
  2. 音频缓存命中会跳过视频下载，当截图需要视频时需强制跳过缓存
  3. `video_path` 为 None 时 `_insert_screenshots()` 静默跳过
- doubao 等多模态模型有 token 限制 — MAX_GRIDS=25 (3x3 拼图时最多 225 帧)，超出会触发 InvalidParameter 错误
- 前端 NoteForm 的 `screenshot` 布尔字段和 `format: ['screenshot']` 是独立的 — 用户只勾格式选项时需后端兜底
- 不要使用硬编码绝对路径（如 `D:/iori/...`）— 所有路径通过 `path_helper` 或相对路径获取
- 后端运行时日志写入位置取决于启动时的 cwd：在项目根目录运行 `python backend/main.py` 会写入 `logs/app.log` 而不是 `backend/logs/app.log`

## ARCH_DECISIONS

- Decision: 使用 yt-dlp 作为统一下载后端，而非各平台独立 SDK
  Reason: 单一依赖管理多平台，避免维护多个下载逻辑。yt-dlp 更新活跃，及时跟进反爬变化
  Alternatives: 各平台独立 API 客户端（维护成本过高）

- Decision: GPT provider 使用工厂模式（`gpt_factory.py`）统一对接多种 LLM
  Reason: 支持用户自由切换模型（OpenAI、DeepSeek、Qwen、doubao 等），无需修改核心业务逻辑
  Alternatives: 每个 provider 独立实现（代码重复，扩展困难）

- Decision: 视频截图使用密集采样 + 场景检测筛选，而非固定间隔提取
  Reason: 固定间隔无法区分关键帧和冗余帧；场景检测基于像素差异评分，选出信息量最大的帧
  Alternatives: 纯固定间隔（信息密度低），AI 分析选帧（成本高）

- Decision: Markdown 下载使用 base64 内嵌图片，而非保留相对路径
  Reason: 容器内运行的路径和用户本地路径不同，相对路径会导致图片丢失
  Alternatives: 绝对 URL（容器内外路径不一致）

## TEST_STRATEGY

- Backend tests live in `backend/tests/` — use pytest
- Test files: `test_note_helper.py`, `test_request_chunker.py`, `test_screenshot_marker.py`, `test_task_serial_executor.py`, `test_universal_gpt_checkpoint.py`, `test_video_reader_dedupe.py`
- Frontend has no project-level test suite — manually verify UI changes
- Run backend tests with: `cd backend && pytest tests/ -v`

## DESIGN_DECISIONS

- API 使用 FastAPI + Pydantic 模型验证 — 所有请求/响应通过 Pydantic schema 定义
- 前端状态管理使用 Zustand stores（taskStore, modelStore, configStore, providerStore）
- 任务状态轮询：前端每 3 秒通过 `useTaskPolling` hook 查询后端
- 视频处理流水线：下载 → 提取音频(FFmpeg) → 转录(Whisper/Groq) → LLM 生成笔记
- 笔记生成结果通过 SQLite 持久化（`bili_note.db`），支持向量存储和检索
