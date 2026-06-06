# Changelog

本项目所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.4.0] - 2026-06-07

### Added

- **可配置 Whisper 模型**：转写设置支持自定义 Whisper 模型与名称映射，可指定自定义 HuggingFace repo 或本地路径（新增 `backend/app/transcriber/whisper_models.py` + 测试），转写设置页可选择 / 配置模型。
- **关注公众号获取交流群**：关于页群二维码改为公众号二维码，关注公众号后回复「交流群」即可获取最新群二维码，避免群码过期失效。

### Fixed

- **浏览器扩展**：修复标题显示异常，优化脑图（Markmap）导出。

### Docs

- **GPU/CUDA 部署**：README 补全 GPU/CUDA 部署说明。

## [2.3.4] - 2026-05-27

### Added

- **一对一搭建服务二维码**：新增「BiliNote AI 笔记系统一对一搭建服务」二维码（README + 关于页），扫码加微信、备注「搭建服务」即可咨询。

## [2.3.3] - 2026-05-22

### Fixed

- **预构建 Docker 镜像数据持久化**：文档的 `docker run` 只挂了 `data/`（媒体缓存），而 SQLite 数据库（LLM 供应商配置 + 笔记历史）和笔记文件不在该卷下，导致删除 / 升级容器时丢失配置与历史。现将数据库重定向到 `/app/backend/data/bili_note.db`、笔记到 `data/note_results`（随 data 卷持久化）；README 更新为挂载 `data` / `config` / `static` / `models` 四个数据卷，并提示**勿**挂整个 `/app/backend`（命名卷会固化镜像内代码，导致 `docker pull` 升级不生效）。`docker-compose` 路径本就正确（`./backend:/app` 整目录绑挂），未受影响。

## [2.3.2] - 2026-05-22

### Fixed

- **后端启动崩溃（Docker）**：`python:3.11-slim` 基础镜像升级到 Debian 13 / glibc 2.41 后，`ctranslate2` 4.5.0 预编译库带「可执行栈」标记被 glibc 拒绝加载（`cannot enable executable stack ... Invalid argument`）。由于 `from faster_whisper import WhisperModel` 在顶层 import，import 失败直接拖垮整个后端启动 → 容器反复重启。升级 `ctranslate2` 4.5.0→4.6.0（wheel 加入 `noexecstack` 链接标志，从二进制层根治）
- **whisper 模型误报「离线模式找不到模型」**：下载（modelscope 自定义目录）与加载（faster-whisper HF cache）布局不一致导致命不中缓存。统一为下载 / 加载 / 完整性检测 / 损坏自愈都走 HF cache 布局，并向后兼容老 modelscope 目录
- **桌面端构建产物版本恒为 2.0.0**：Release 工作流在 `pnpm tauri build` 前从 git tag 注入版本号到 `tauri.conf.json`，使产物版本与 Release 版本对齐

## [2.3.1] - 2026-05-22

### Changed

- **更新微信交流群二维码**：旧二维码即将失效，替换 README 中 5 个交流群（群 1-5）的入群二维码。

## [2.3.0] - 2026-05-14

主线：一波部署与运行时韧性专项——Docker / 桌面端 / 在线引擎三端的"装不上、起不来、跑一半挂"问题集中清理，并新增全局代理与转写模型就绪门禁。

### Added

- **全局代理**：新增 `ProxyConfigManager`（`config/proxy.json` 持久化 + `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` 环境变量兜底）。一处配置同时作用于 LLM API、转写 API（Groq 等）、yt-dlp 视频下载、youtube-transcript-api 字幕拉取。前端「设置 → 下载配置」页新增代理卡片，会显示当前实际生效值（含 env 兜底来源提示）
- **转写模型就绪门禁**：`/generate_note` 在排队前检查本地转写引擎（fast-whisper / mlx-whisper）的模型是否已下载完整，未就绪直接拦截并返回 `reason=transcriber_model_not_ready`，不再让任务静默卡在首次大文件下载；前端引导用户去「音频转写配置」页下载
- **桌面端后端健康监控韧性**：Tauri 侧 spawn sidecar 后以 HTTP 探针轮询 `/api/sys_check` 判就绪并 emit `backend-ready`；`RunEvent::Exit` 钩子在 app 退出前 kill sidecar，杜绝孤儿进程占用 8483 端口；启动失败对话框展示原因 + 最近 stderr + 一键重启 / 复制日志
- `/sys_health` 重构为结构化健康响应 `{backend, ffmpeg, db, whisper_model}`；部署监控页显示 Whisper 模型本地下载状态
- 所有 Dockerfile 新增 `BASE_REGISTRY` build-arg，国内拉不到 docker.io 时可换 daocloud 等镜像源

### Fixed

- **whisper 模型损坏自愈**：`model.bin` 截断 / 损坏导致 `Unable to open file 'model.bin'` 死循环——加载失败时删除损坏目录、重新下载、重试一次；mlx-whisper 同样按 `config.json` 判定完整性
- **空 API Key 天书报错**：空 key 会让 httpx 拼出非法 header `Bearer ` 并抛 `LocalProtocolError: Illegal header value b'Bearer '`。新增 `build_openai_client` 在入口校验，给出「xxx 的 API Key 未配置」的清晰提示
- **新模型 temperature 不兼容**：OpenAI o1 / o3 / gpt-5 系列拒绝自定义 `temperature`，命中后就地去掉该参数重试，不消耗重试预算
- **桌面端「后端加载中」死循环**：`useCheckBackend` 重写——60s 总超时取代 `while(true)` 无限轮询，订阅 Tauri `backend-ready` / `backend-terminated` / `backend-startup-timeout` 事件；裸 `fetch` 探测避免启动期 toast 叠堆
- **CORS 漏配桌面端 origin**：补全 `tauri://localhost` / `https://tauri.localhost`，修桌面端 fetch 拿到 200 却被浏览器 CORS 拒绝读响应（表现为"连不上后端"但后端日志全 200）
- `/api/api/sys_health` 双 `/api` 前缀导致健康检查 404
- `docker-compose` 的 `restart: on-failure:3` 改为 `unless-stopped`，避免短暂崩溃后容器被永久打死；GPU compose 补齐 `healthcheck` / `restart` / `mem_limit`
- `Dockerfile.complete` 的 supervisord 用 `%(ENV_*)s` 透传环境变量给 backend 子进程（此前只白名单 2 个，`docker run -e` 配的变量后端看不到）
- `.env.example`：修正 `VITE_API_BASE_URL` 端口（8000→8483）、`WHISPER_MODEL_SIZE`（medium→tiny，首次启动不被 ~1.5GB 下载卡住）
- Onboarding：第 1 步后端连通检测改为自动重试 + Tauri 事件触发 + 手动重检按钮；第 2 步撞预置供应商名时改为更新已存在供应商而非报错
- 模型供应商列表卡片整行可点击切换（此前仅 icon 区域响应）
- `connect_test` 改用真实 chat completion 探测而非 `/v1/models`（后者在 key 无 inference 权限 / 供应商不实现该端点时会误判）

### Internal

- `backend/main.py` lifespan 拆为 `[startup 1/5]…[startup 5/5]` 分段日志，启动期异常可一眼定位死在哪一步
- `request.ts` 新增 `suppressToast` 配置位，预期内的失败（如 onboarding 撞名重试）不弹全局红 toast
- `CLAUDE.md` 勘误：移除不存在的 `app/messaging/` / `app/i18n/` / `worker_registry.py` 描述，修正 `events/` 路径，补 `pytest` / 前端 `typecheck` 命令

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
