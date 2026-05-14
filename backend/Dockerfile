# BASE_REGISTRY 默认走 docker.io；国内拉不到 docker.io 时可换 daocloud / 阿里云 / 自建镜像源：
#   docker-compose build --build-arg BASE_REGISTRY=docker.m.daocloud.io
# 或写到 docker-compose.yml 的 build.args / 环境变量里
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/library/python:3.11-slim

ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

RUN rm -f /etc/apt/sources.list && \
    rm -rf /etc/apt/sources.list.d/* && \
    echo "deb https://${APT_MIRROR}/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://${APT_MIRROR}/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://${APT_MIRROR}/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/bin:${PATH}"
ENV HF_ENDPOINT=https://hf-mirror.com

WORKDIR /app

# 先复制 requirements.txt 利用层缓存
COPY ./backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i ${PIP_INDEX} -r requirements.txt

# 再复制应用代码（频繁变动不影响 pip 缓存层）
COPY ./backend /app

CMD ["python", "main.py"]
