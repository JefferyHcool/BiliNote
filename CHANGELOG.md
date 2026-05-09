# Changelog

本项目所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.2.3] - 2026-05-09

### Fixed

- 前端 vite build 在 Docker / Tauri CI 中失败：`Rollup failed to resolve import '@tauri-apps/api/event'`。v2.2.0 加的 P1/P2 桌面端组件用了 `await import('@tauri-apps/api/event')` 与 `'@tauri-apps/api/core'`，但 `@tauri-apps/api` 只是 `@tauri-apps/plugin-shell` 的间接依赖，没在 `BillNote_frontend/package.json` 直接声明，Rollup 在 production build 时静态分析报"无法解析"
  - `BillNote_frontend/package.json`：把 `@tauri-apps/api` 加为直接依赖（`^2.10.1`，与 lockfile 中已有的 transitive 版本一致）
  - 本地 `DOCKER_BUILD=1 pnpm run build` 复现 + 验证修复

## [2.2.2] - 2026-05-09

补 v2.2.1 漏掉的 Tauri 桌面端 build 修复。

### Fixed

- 桌面端 Tauri 构建失败：v2.2.1 的 hotfix 只修了 Docker 镜像构建里的 pnpm 版本，`main.yml` 的 `pnpm/action-setup@v4 with: version: 'latest'` 没改，于是桌面端 build 仍然在 `Install frontend dependencies` 步报 `ERR_UNKNOWN_BUILTIN_MODULE: No such built-in module: node:sqlite`（pnpm 11 要求 Node 22+，但 main.yml 用的 node 20）。pin 到 `9.15.0`，与 Docker 侧一致。

## [2.2.1] - 2026-05-09

补 v2.2.0 ghcr.io 镜像构建失败。

### Fixed

- Docker 镜像构建失败：`v2.2.0` tag 触发的 ghcr.io 推送在 frontend-builder 第 5/7 步 `pnpm install --frozen-lockfile` 报 `ERR_UNKNOWN_BUILTIN_MODULE`。根因：`corepack prepare pnpm@latest` 拉到了 pnpm 11.0.9，而 pnpm 11 要求 Node 22+，跟我们的 `node:20-alpine` 不兼容。
  - `Dockerfile.complete` 与 `BillNote_frontend/Dockerfile` 的 pnpm 版本 pin 到 `9.15.0`（lockfile 由 pnpm 9 生成，匹配 Node 20）

## [2.2.0] - 2026-05-09

主线：浏览器插件功能与 web 端 NoteForm 完整对齐；桌面客户端 UX 与错误恢复一波重炼。

### Added — 浏览器插件

- 笔记选项与 web 端 NoteForm 完整对齐：
  - `style` 由自由文本改成 9 个预设下拉（minimal / detailed / academic / tutorial / xiaohongshu / life_journal / task_oriented / business / meeting_minutes），与 backend `prompt_builder.note_styles` 严格匹配（之前自由文本不命中 enum 等于没传——隐性 bug）
  - `format` 完整 4 个 checkbox（toc / link / screenshot / summary，原来只有 screenshot/link）
  - `extras` 文本框：拼接到 prompt 末尾的 ad-hoc 提示
- 多模态视频理解：`video_understanding` 开关 + `video_interval`（1-30 秒）+ `grid_size`（[r,c]，1-10），抽帧拼图喂视觉模型，提示需选视觉模型才生效

### Added — 桌面客户端

- **首启 4 步引导**（`/onboarding`）：后端连通性自检 → LLM 供应商 + 模型 → 转写引擎选择（默认推荐 Groq）→ Cookie 同步说明。完成后 `localStorage('bilinote-onboarded')` 标记，纯 web 端不打扰
- **Sidecar 健康度面板**：右下角浮动状态点（绿/黄/红，5s 轮询 `/sys_health`），点开抽屉看最近 200 行后端日志、一键重启后端（新增 Tauri command `restart_backend_sidecar`）、复制日志
- **启动期路径诊断**：Tauri `setup` 中检测安装路径含非 ASCII / 含空格 / 父目录不可写时，emit `backend-warning` 让前端顶端横幅显式告警，主动暴露 README 长期文字警告但无防御的"中文路径"等坑

### Changed

- Whisper 默认模型 size 从 `medium`（~1.5GB）改为 `tiny`（~75MB）：新装用户没主动设置时不再卡在首次大模型下载；高精度可在「音频转写配置」页主动切
- 切到 `fast-whisper` / `mlx-whisper` 且当前 size 未下载时，「音频转写配置」页保存前 confirm 体积提示，并推荐改用在线引擎
- Tauri sidecar 启动逻辑抽出 `spawn_backend_sidecar()`；child handle 存进 `SidecarHandle` state 以支持后续 restart
- sidecar stdout/stderr emit 时不再用 `format!("'{}'", ...)` 包引号，原文直传（前端 hook 兼容旧格式兜底剥引号）

### Fixed

- WhisperTranscriber 在半成品模型目录上死循环报 `Unable to open file 'model.bin'`：判定从「目录存在」改为「`model.bin` 落盘」，半成品目录会被识别并重新下载（PR `fix/backend-deploy-resilience`）
- `/api/deploy_status` 在没装 torch 的部署上 `ModuleNotFoundError: No module named 'torch'` 500：torch 改 try/except，未装时返回 `{available: false, torch_installed: false}`；transcriber 配置 + ffmpeg 也都裹 try，单项失败不再打死整个监控页（同上 PR）
- `routers/config._check_whisper_model_exists` 同步改用 `model.bin` 判定，避免「已下载」状态在监控页误报

## [2.1.4] - 2026-05-07

CI 工程化修复，无运行时行为变化。

### Internal

- 桌面端 Tauri 构建矩阵去掉 Linux（`ubuntu-22.04 / x86_64-unknown-linux-gnu`）。Linux 桌面端构建持续 17m+，且无对应分发渠道；Linux 用户继续可以走 Docker 镜像 (`ghcr.io/jefferyhcool/bilinote`)
- commitlint workflow 去掉无效的 `firstParent` input（wagoid/commitlint-github-action@v6 不支持，被忽略并打 warn）
- 规范 release merge commit 标题：`chore(release): vX.Y.Z`（合 master）/ `chore(release): merge release/X.Y.Z back into develop`（回灌 develop），让 commitlint 能正确识别。`RELEASING.md` §3 与 `CONTRIBUTING.md` §6.3 同步更新

## [2.1.3] - 2026-05-07

### Fixed

- DeepSeek 等非多模态供应商被 400 拒绝（issue #282）：`UniversalGPT.create_messages` 与 `_build_merge_messages` 此前**无条件**把 content 拼成 OpenAI 多模态数组 `[{"type":"text",...}]`，DeepSeek `deepseek-chat` 等模型不识别 `image_url` 变体直接报 `invalid_request_error`。`GPTFactory.from_config` 一律实例化 `UniversalGPT`，所以问题覆盖**所有**通过模型设置页接入的非多模态供应商，不止 DeepSeek。
  - 现按 `video_img_urls` 是否非空切换 content 形态：有图保留多模态数组（视觉模型不退化），无图退回 string。合并阶段历来不带图，统一改 string。
  - 与同包内 `deepseek_gpt.py` / `openai_gpt.py` / `qwen_gpt.py` 的 message builder 行为对齐。
  - 新增 `backend/tests/test_universal_gpt_content_format.py` 6 个 case 回归覆盖（含 `image_url` 字面 not-in JSON 断言）。

感谢 @voidborne-d 的修复（#345）。

## [2.1.2] - 2026-05-07

补 v2.1.1 上 ghcr.io 镜像构建失败的坑。

### Fixed

- Docker 镜像构建失败：v2.1.1 tag 触发的 ghcr.io 推送在 frontend-builder 第 7/7 步 `pnpm run build` 挂掉（vite `loadConfigFromBundledFile` 加载 `@tailwindcss/vite` plugin 时 1.5s 内异常退出）。
  - `Dockerfile.complete` 与 `BillNote_frontend/Dockerfile` 升 `node:18-alpine` → `node:20-alpine`：Tailwind v4 已不再支持 Node 18，Vite 6 也推荐 Node 20+
  - `Dockerfile.complete` 的 frontend 阶段同时复制 `pnpm-lock.yaml` 并改用 `--frozen-lockfile`，杜绝每次构建重解析 semver 拉到比本地新的 native dep
  - `BillNote_frontend/pnpm-lock.yaml` 强制入库（之前一直未提交，导致 CI / 本地依赖图持续漂移）
- README 联系社区段补上微信群二维码（之前只写"年会恢复更新以后放出最新社区地址"）

## [2.1.1] - 2026-05-07

工程化与文档收尾，无运行时行为变化。

### Added

- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — 贡献指南，落地简化 Git Flow（master + develop + 短生命周期分支）+ 提交规范 + 合并规范
- [`RELEASING.md`](./RELEASING.md) — 发版手册（Release Manager 视角），含 release/* 流程 + 各商店人工上传步骤 + 自动发布所需 secrets
- `.github/ISSUE_TEMPLATE/{config,bug_report,feature_request}.yml` — 表单形式的 issue 模板，按工作区分类
- `.github/pull_request_template.md` — PR 模板，把 CONTRIBUTING §5.2 落成 checklist
- `.commitlintrc.json` + `.github/workflows/commitlint.yml` — commitlint CI（PR + push develop/master 时校验，自定义 type 白名单，兼容中文 subject）
- `.github/workflows/release-extension.yml` — `v*` tag push 时自动构建插件 .zip / .xpi / .crx 并挂到对应 GitHub Release（商店自动发布以注释形式预留）

### Changed

- 关于页二维码改为 `import @/assets/wechat.png`，不再依赖腾讯云 COS CDN，更新只需替换文件 + 跑构建
- 群聊 QR 替换为最新版本（`doc/wechat.png` + `BillNote_frontend/src/assets/wechat.png`）

### Removed

- 关于页 QQ 群联系方式（号 785367111，已不再活跃维护）
- 旧版 `.md` 格式 issue 模板（被新 yml 表单模板取代）

## [2.1.0] - 2026-05-07

本次发布的主线是**浏览器插件**和 **B 站字幕优先链路**。配合一些后端 / 前端体验修复。

### Added — 浏览器插件 (`BillNote_extension/`)

全新 Chrome / Edge / Firefox MV3 扩展。Vue 3 + Vite + UnoCSS，骨架基于 vitesse-webext。

- **入口四件套**
  - 工具栏 popup：识别当前 tab → 一键提交，紧凑展示标题 + 封面 + 进度
  - 视频页悬浮按钮：仅在支持平台注入，点击即触发任务
  - 右键菜单"用 BiliNote 总结此视频"：限定 4 个支持域名
  - 侧边栏（side panel）：详情视图 + 三模式切换
- **侧边栏三视图**
  - Markdown：渲染笔记，复制 / 下载 .md
  - 思维导图：基于 markmap-lib + markmap-view 的可缩放 mind map
  - AI 问答：复用后端 RAG `/chat/index`、`/chat/status`、`/chat/ask` 三件套，自动索引 + 多轮历史
- **设置页五大块**（搬入 web 端全部配置能力，今后插件即配置中心）
  - 通用：后端地址、连通性测试、默认供应商 / 模型 / 画质 / 截图 / 跳转 / 风格
  - 模型供应商：完整 CRUD、启用切换、连接测试、模型增删
  - 音频转写配置：fast-whisper / mlx-whisper / Groq / 必剪 / 快手 切换、Whisper 模型大小、本地下载状态、触发下载
  - 下载配置：每平台 cookie 显示、浏览器一键同步、手动粘贴
  - 部署监控：后端 / FFmpeg / CUDA / Whisper 状态总览
- **浏览器 cookie 直通**：`chrome.cookies.getAll` 一键把 `.bilibili.com` 等域 cookie 同步到后端 `/api/update_downloader_cookie`
- **B 站字幕浏览器抓取**：插件直接调 player API 拿字幕，借 host_permissions 自动带本地登录态 cookie，绕过 CORS；随提交以 `prefetched_transcript` 字段附给后端，后端跳过 `download_subtitles` + 音频转写，直接进 GPT 总结

### Added — 后端

- `BilibiliSubtitleFetcher`（`app/downloaders/bilibili_subtitle.py`）：直接调 B 站 player API 拿字幕，作为非插件场景下 yt-dlp 路径的更可靠替代
- `VideoRequest.prefetched_transcript` 字段：客户端预取的字幕直接落到 `<task_id>_transcript.json`，NoteGenerator cache-hit 自动复用

### Added — 前端 Web

- Zustand persist 迁移到 IndexedDB（#318）

### Changed

- 后端 CORS：从静态 origin 列表改为 regex，兼容 `chrome-extension://`、`moz-extension://`、`localhost`、`tauri.localhost`
- mlx-whisper 仓库 ID 改用 `MLX_MODEL_MAP`：`whisper-{size}-mlx` 命名（`large-v3-turbo` 例外），不再 hardcode 出 404
- BilibiliDownloader 从 `CookieConfigManager` 读取 cookie 并注入 yt-dlp cookiefile（#333）
- CLAUDE.md 补充 v2.0.0 引入的子系统说明（RAG / Chat、可选 Nacos+RabbitMQ、i18n、cookie/transcriber 管理器）以及浏览器插件 workspace

### Fixed

- AILogo：自定义供应商（`logo='custom'`）走兜底渲染时不再误报 `console.error`，未匹配的名称降级为 warn
- SettingPage `Model.tsx` 双栏布局加 `min-h-0 overflow-y-auto`：供应商列表过长时无法滚动
- 供应商开关切换不能实时生效（#336）
- `/get_all_providers` 中 301 行历史伪内置脏数据清理 + `add_provider` 加防御（强制 `type='custom'`、同名查重、错误向上抛）
- `/api/task_status` 拆 ResponseWrapper：插件侧进度条因未拆 `data` 全灰；同时把 `R.error` 翻译为 `status:'FAILED'`，避免 UI 卡在轮询循环
- ESLint / ESM `__dirname` 在 production build 中未定义（多个 docker / vite 配置修复）
- GitHub Actions 构建错误 + apt-get 安装失败 + 删除仓库内 ffmpeg 二进制
- 渲染时剥掉 backend 注入的 `> 来源链接：URL` 行（与 web 端 MarkdownViewer 一致），导出文件保留原行便于溯源
- 侧边栏布局收紧：完成后不再渲染 8 段进度条；标题压成单行；视图切换 + 复制 / 下载并入一行；历史任务从底部 details 改为顶栏下拉

### Internal

- 新增分支策略：`develop` / `release/x.y.z` / `master` git-flow
- 备份 backend SQLite DB 前 / 清理脏数据后均落盘存档
