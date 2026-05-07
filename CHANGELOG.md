# Changelog

本项目所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
