# === 前端构建阶段 ===
FROM node:18-alpine AS builder

# 安装 pnpm
RUN npm install -g pnpm

# 设置工作目录
WORKDIR /app

# 拷贝前端源码
COPY ./BillNote_frontend /app

# 安装依赖并构建
RUN pnpm install && pnpm run build

# --- 阶段2：使用 nginx 作为静态服务器 ---
FROM nginx:1.25-alpine

# 删除默认配置（可选）
RUN rm -rf /etc/nginx/conf.d/default.conf
COPY ./BillNote_frontend/deploy/default.conf /etc/nginx/conf.d/default.conf


# 拷贝构建产物
COPY --from=builder /app/dist /usr/share/nginx/html