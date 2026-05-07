# 贡献指南

欢迎为 BiliNote 贡献代码。本文档约定分支管理、提交规范、合并流程。新贡献者请通读一遍后再开 PR。

> 关联文档
> - [README.md](./README.md)：项目概览、快速开始
> - [CLAUDE.md](./CLAUDE.md)：仓库结构 + 各 workspace 开发命令
> - [CHANGELOG.md](./CHANGELOG.md)：版本变更记录
> - [RELEASING.md](./RELEASING.md)：发版执行手册（Release Manager 视角）

---

## 1. 仓库结构与工作区

本仓库为多工作区单体仓：

| 路径 | 内容 | 主要命令 |
|---|---|---|
| `backend/` | Python 3.11 + FastAPI | `pip install -r requirements.txt && python main.py` |
| `BillNote_frontend/` | React 19 + Vite | `pnpm install && pnpm dev` |
| `BillNote_extension/` | Vue 3 + Vite + WebExtension MV3 | `pnpm install && pnpm dev` |

详细结构与开发命令见 [CLAUDE.md](./CLAUDE.md)。提交时**单 PR 不要跨多个工作区做无关改动**，便于评审与回滚。

---

## 2. 分支模型

采用简化 Git Flow：稳定主干 `master` + 长期开发集成 `develop` + 短生命周期业务分支。

| 分支类型 | 命名 | 长期保留 | 创建来源 | 合并去向 | 用途 |
|---|---|---|---|---|---|
| 生产主干 | `master` | ✅ | 仓库默认分支 | — | 始终保持可发布状态；只接收 `release/*` 与 `hotfix/*` 合入 |
| 开发主干 | `develop` | ✅ | `master` | `release/*` 回灌后 | 日常需求集成；常规开发都从这里起 |
| 功能分支 | `feature/*` | ❌ | `develop` | `develop` | 新功能 / 需求开发 |
| 修复分支 | `fix/*` | ❌ | `develop` | `develop` | 开发期间发现的缺陷修复（非线上问题） |
| 发布分支 | `release/*` | ❌ | `develop` | `master` + `develop` | 版本冻结、回归、发版准备 |
| 热修复 | `hotfix/*` | ❌ | `master` | `master` + `develop` | 线上紧急问题 |

### 基本原则

- `master` 只保存**已发布代码**，不接受日常开发提交。
- `develop` 是**唯一**长期开发集成分支。
- 所有业务开发**必须**用短生命周期分支，禁止长期占用个人开发分支。
- 一个分支只承载一个需求或一类明确的修复事项。

---

## 3. 分支命名

### 命名格式

```
feature/<scope>-<事项>
fix/<scope>-<事项>
release/<版本号>
hotfix/<scope>-<事项>
```

`<scope>` 优先用代码 scope（与 commit message scope 对齐，见 §5），常用：

- `extension` — 浏览器插件（`BillNote_extension/`）
- `frontend` — Web 前端（`BillNote_frontend/`）
- `backend` — Python 后端（`backend/`）
- `bilibili` / `youtube` / `douyin` / `kuaishou` — 平台特定改动
- `transcriber` — 音频转写
- `gpt` / `chat` — LLM / RAG
- `docker` / `ci` — 构建与发布
- `docs` — 文档

### 命名示例

```bash
# 功能开发
feature/extension-side-panel
feature/youtube-subtitle-innertube
feature/backend-rag-chat

# 开发期修复
fix/extension-task-status-unwrap
fix/bilibili-cookie-injection
fix/mlx-whisper-repo-id

# 发版
release/2.1.0
release/2.2.0

# 线上热修
hotfix/backend-cors-regex
hotfix/frontend-provider-switch
```

### 命名要求

- 全小写字母 / 数字 / 中划线
- `<事项>` 要表达**具体行为**，避免 `test` / `update` / `temp` / `wip` 这类无意义名
- `release/<版本号>` 必须与实际 tag 一致（如 `release/2.1.0` ↔ `v2.1.0`）

---

## 4. 标准协作流程

### 4.1 日常需求开发

```bash
git checkout develop
git pull origin develop
git checkout -b feature/<scope>-<事项>

# … 开发 + 自测 + commit …

git push -u origin feature/<scope>-<事项>
# 在 GitHub 上发起 PR：base = develop，compare = 你的分支
```

合并通过且 PR closed 后，**删除本地与远端分支**：

```bash
git branch -d feature/<scope>-<事项>
git push origin --delete feature/<scope>-<事项>
```

### 4.2 开发期缺陷修复

提测或联调中发现问题时，从 `develop` 切 `fix/*`。**不要在原 `feature/*` 上长期叠加零散修复**。

适用场景：
- 已合入 `develop` 后被测试打回的问题
- 多个功能集成后暴露的兼容性问题
- 非线上环境问题

### 4.3 版本发布

```bash
# 1. 从 develop 切 release
git checkout develop && git pull origin develop
git checkout -b release/<版本号>

# 2. 在 release 分支上：更新 README 版本号、写 CHANGELOG.md、必要的小修
git commit -am "docs: <版本号> CHANGELOG + README 版本"
git push -u origin release/<版本号>

# 3. 进入冻结期，PR base=master 合并；同时 PR base=develop 回灌
# 4. master 上打 tag
git checkout master && git pull
git tag -a v<版本号> -m "BiliNote v<版本号>" && git push origin v<版本号>

# 5. release 分支已合入两边，删除
git push origin --delete release/<版本号>
```

要点：
- **冻结期内 `release/*` 不再合入新需求**，只允许修复发布缺陷。
- 发版窗口期内的新需求继续基于 `develop` 开发，**不进入当前 `release/*`**。
- 发布完成后必须把 `release/*` 同步回 `develop`，避免漏修。

### 4.4 线上紧急修复

```bash
git checkout master && git pull
git checkout -b hotfix/<scope>-<事项>
# … 修 + commit …
# PR base=master，合入后立刻打 patch tag（如 v2.1.1）发版
# 同一改动同时 PR base=develop 回灌
```

要点：
- `hotfix/*` 仅处理**线上阻断性 / 高优先级**缺陷。
- 非紧急问题不得绕过 `develop` 直接走热修流程。
- 若当前存在 `release/*` 即将发布，需评估是否同步到对应 release，避免修复丢失。

---

## 5. 提交规范

### 5.1 Commit message 格式

> CI 已接入 [commitlint](https://commitlint.js.org)（[`.commitlintrc.json`](./.commitlintrc.json) + [`.github/workflows/commitlint.yml`](./.github/workflows/commitlint.yml)）。
> PR 上所有 commit 都会被校验，type 不在白名单时合并按钮会被卡。

```
type(scope): subject
```

例：

```
feat(extension): 侧边栏接入思维导图（markmap）与 RAG 问答
fix(bilibili): 修正字幕优先链路在未登录态下的回退
docs(contributing): 新增贡献指南
chore(ci): 优化 docker 构建缓存
```

#### type

| type | 说明 |
|---|---|
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档变更 |
| `style` | 代码风格调整（不影响行为） |
| `refactor` | 重构（非 feat / 非 fix） |
| `perf` | 性能优化 |
| `test` | 测试增删 |
| `build` | 构建系统 / 依赖变更 |
| `ci` | CI 配置变更 |
| `chore` | 杂项（不归入以上类别） |
| `ui` | 界面 / 交互层调整（仓库内既有用法） |
| `revert` | 回滚 |

#### scope

与 §3 的分支 scope 保持一致：`extension` / `frontend` / `backend` / `bilibili` / `youtube` / `douyin` / `kuaishou` / `transcriber` / `gpt` / `chat` / `docker` / `ci` / `docs` 等。

#### subject

- 用中文或英文都可以，**保持一种风格**。
- 用现在时陈述（"新增 X" / "修复 Y" / "Add X" / "Fix Y"）。
- 首字母不大写，结尾不加句号。
- 单行控制在 72 字符以内；如需详细说明，正文与标题之间空一行。

### 5.2 PR 标题与正文

- **PR 标题**沿用 commit message 格式，描述本次 PR 的总体改动。
- **PR 正文**应包含：
  - 改动的"为什么"（背景 / issue / 用户场景）
  - 改动的"做了什么"（关键文件、关键决策）
  - **测试方式**（如何验证、覆盖了哪些 case）
  - **回归风险**与影响面
  - 是否需要后端 / 前端 / 配置同步部署

---

## 6. 合并规范

### 6.1 合并前要求

- 合并前必须**先同步**目标分支最新代码（`git pull --rebase` 或在 PR 上点 "Update branch"）。
- 合并前必须完成**自测**，确保核心流程可用。
- 后端改动需 `python -m py_compile` 至少通过；前端 / 插件改动需 `pnpm typecheck && pnpm build` 通过。
- **冲突由分支负责人解决**，不得留给评审人或发版人员。

### 6.2 评审

- 默认通过 PR 合并，**不允许**绕过 PR 直接 push 到 `master` 或 `develop`。
- 评审人至少关注：业务影响、回归风险、是否夹带无关改动、目录归属是否合理。
- 修文档 / 改注释这种小变更允许 1 人评审通过；改业务逻辑 / 协议 / 共享模块至少 2 人评审。

### 6.3 合并方式

- `feature/*` / `fix/*` 合入 `develop`：推荐 **Squash and merge**，保持 develop 历史线性。
- `release/*` 合入 `master` 与回灌 `develop`：使用 **Merge commit (--no-ff)**，保留发版结构。
  · merge commit 标题用 `chore(release): vX.Y.Z`（合 master）或 `chore(release): merge release/X.Y.Z back into develop`（回灌 develop），保证 commitlint 通过。
- `hotfix/*` 同上 release。

### 6.4 合并后

- 短期分支合并完成后**必须删除**（远端 + 本地）。
- 已完成的分支不得继续承接新需求；如需后续迭代请重新基于最新目标分支开新分支。

---

## 7. Git 钩子注意事项

`BillNote_extension/` 早期使用 `simple-git-hooks` 的 `postinstall`，会在仓库根目录 `.git/hooks/pre-commit` 注入 `pnpm lint-staged`，但仓库根没有 `package.json`，导致**任何 commit 都被钩子卡死**。**已在 v2.1.0 起移除**该 postinstall 配置。

如果你机器上还残留旧版本装下来的 hook：

```bash
# 一次性清理
rm .git/hooks/pre-commit

# 或临时绕过本次 commit
SKIP_SIMPLE_GIT_HOOKS=1 git commit -m "..."
```

---

## 8. 版本号与 CHANGELOG

- 版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`
  - `MAJOR`：破坏性 API 变更或重大重构
  - `MINOR`：新增特性、向后兼容
  - `PATCH`：bug 修复、向后兼容
- 每次发版**必须更新 [CHANGELOG.md](./CHANGELOG.md)**，按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式分类（Added / Changed / Fixed / Removed / Security / Internal）。
- 发版同时更新 `README.md` 顶部的版本号与"v\<版本号\> 新增"摘要段。
- `master` 上打 tag 形如 `vX.Y.Z`，注释中包含本次发布主线 + 引用 `CHANGELOG.md`。

---

## 9. 禁止事项

- ❌ 直接在 `master` 上开发、提交、修复普通问题
- ❌ 新增长期 `dev-*` / `wip-*` / `<姓名>-dev` 个人分支作为日常协作分支
- ❌ 一个分支同时承载多个需求 / 多个缺陷 / 跨版本内容
- ❌ 未评审、未自测、未通过基础校验直接合并
- ❌ `release/*` 冻结后继续混入新需求
- ❌ `hotfix/*` 只合入 `master` 而不回灌 `develop`
- ❌ 提交 / 仓库内包含密钥、API key、`.env` 等敏感文件
- ❌ 提交 `node_modules/` / `dist/` / `extension/dist/` / `__pycache__/` / 大型二进制（参考各级 `.gitignore`）

---

## 10. 历史分支迁移

仓库历史上存在多条已合并但未删除的分支（见 `git branch -a`）。即日起：

- 不再创建 `dev-*` / `<姓名>-*` 个人分支
- 已合入主干的旧分支，由发版人统一清理
- 未完成需求应尽快迁移到符合 §3 命名规范的新分支

---

## 11. 推荐流程图

```text
master  ←  hotfix/*       (线上紧急修复)
  ↑           ↑
  │           │
release/*  ←  develop  ←  feature/*       (功能开发)
  │           ↑
  └───────────┘
        fix/*                              (开发期修复)
        回灌
```

---

## 12. 执行口径速查

| 场景 | 流程 |
|---|---|
| 新功能 | `develop` → `feature/*` → `develop` |
| 提测后发现问题 | `develop` → `fix/*` → `develop` |
| 版本发布 | `develop` → `release/*` → `master` + `develop`；打 tag |
| 线上紧急故障 | `master` → `hotfix/*` → `master` + `develop`；打 patch tag |
| 发版期内新需求 | 基于 `develop` 开 `feature/*`，**不**进入当前 `release/*` |

---

如有改进建议，欢迎开 PR 修订本文档（`docs(contributing): ...`）。
