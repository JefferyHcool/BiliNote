<!--
PR 标题请遵循 type(scope): subject 格式，例如：
  feat(extension): 侧边栏接入思维导图
  fix(bilibili): 修正字幕优先链路在未登录态下的回退
分支命名 / 提交规范见 CONTRIBUTING.md。
-->

## 改动概述

<!-- 一句话说清这个 PR 做了什么 -->

## 为什么

<!-- 背景、关联 issue（Fixes #xxx / Refs #xxx）、用户场景 -->

## 做了什么

<!-- 关键文件、关键决策。可贴关键片段或截图 -->

## 测试方式

- [ ] `pnpm typecheck && pnpm build`（前端 / 插件）通过
- [ ] `python -m py_compile <文件>` 或本地 backend 启动验证（后端）通过
- [ ] 手动验证步骤：
  <!-- 描述如何复现验证；UI 改动请附截图 / 录屏 -->

## 回归风险

<!-- 影响面、可能受波及的功能、是否需要前后端 / 配置 同步部署 -->

## Checklist

- [ ] 分支命名遵循 [CONTRIBUTING.md §3](../CONTRIBUTING.md#3-分支命名)（`feature/*` / `fix/*` / `release/*` / `hotfix/*`）
- [ ] base 分支正确（常规改动 → `develop`；线上紧急 → `master`；发版 → 见 §4.3）
- [ ] Commit message 遵循 `type(scope): subject` 格式（[CONTRIBUTING.md §5.1](../CONTRIBUTING.md#51-commit-message-格式)）
- [ ] 已自测核心流程
- [ ] 已更新相关文档（`README.md` / `CHANGELOG.md` / `CLAUDE.md` / 模块 README，如适用）
- [ ] 未夹带 secrets / `.env` / 大型二进制
- [ ] 单 PR 不跨多个工作区做无关改动
