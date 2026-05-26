# === 前端构建阶段 ===
# Tailwind v4 / Vite 6 需要 Node 20+，alpine + pnpm 会按 lockfile 拉 musl native binary。
# BASE_REGISTRY 默认 docker.io，国内拉不到可换 daocloud / 阿里云镜像：
#   docker-compose build --build-arg BASE_REGISTRY=docker.m.daocloud.io
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/library/node:20-alpine AS builder

# 可由发布 workflow 从 git tag 注入，用于前端 About 页展示版本；未传时由 Vite 回退读取 tauri.conf.json。
ARG VITE_APP_VERSION=
ENV VITE_APP_VERSION=${VITE_APP_VERSION}

# pnpm pin 到 9.x：lockfile 是 v9 生成；pnpm 11 要求 Node 22+ 与 node:20 不兼容
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app

# 先复制 lockfile 利用依赖层缓存
COPY ./BillNote_frontend/package.json ./BillNote_frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 再复制源代码并构建
COPY ./BillNote_frontend/ ./
RUN pnpm run build

# --- 阶段2：使用 nginx 作为静态服务器 ---
# 重新声明 ARG —— buildkit 跨阶段不自动继承
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/library/nginx:1.25-alpine

RUN rm -rf /etc/nginx/conf.d/default.conf
COPY ./BillNote_frontend/deploy/default.conf /etc/nginx/conf.d/default.conf

# 拷贝构建产物
COPY --from=builder /app/dist /usr/share/nginx/html
