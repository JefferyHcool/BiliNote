<div style="display: flex; justify-content: center; align-items: center; gap: 10px;
">
    <p align="center">
  <img src="./doc/icon.svg" alt="BiliNote Banner" width="50" height="50"  />
</p>
<h1 align="center" > BiliNote v2.0.0</h1>
</div>

<p align="center"><i>AI 视频笔记生成工具 让 AI 为你的视频做笔记</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" />
  <img src="https://img.shields.io/badge/frontend-react%2019-blue" />
  <img src="https://img.shields.io/badge/backend-fastapi-green" />
  <img src="https://img.shields.io/badge/GPT-openai%20%7C%20deepseek%20%7C%20qwen-ff69b4" />
  <img src="https://img.shields.io/badge/docker-ghcr.io-blue" />
  <img src="https://img.shields.io/badge/status-active-success" />
  <img src="https://img.shields.io/github/stars/jefferyhcool/BiliNote?style=social" />
</p>



## ✨ 项目简介

BiliNote 是一个开源的 AI 视频笔记助手，支持通过哔哩哔哩、YouTube、抖音等视频链接，自动提取内容并生成结构清晰、重点明确的 Markdown 格式笔记。支持插入截图、原片跳转、AI 问答等功能。

## 📝 使用文档
详细文档可以查看[这里](https://docs.bilinote.app/)

## 体验地址
可以通过访问 [这里](https://www.bilinote.app/) 进行体验，速度略慢，不支持长视频。

## 📦 桌面版下载
本项目提供了 Windows 和 macOS 桌面客户端，可在 [Releases](https://github.com/JefferyHcool/BiliNote/releases) 页面下载最新版本。

> Windows 用户请注意：一定要在没有中文路径的环境下运行。

## 🔧 功能特性

- 支持多平台：Bilibili、YouTube、本地视频、抖音、快手
- 支持返回笔记格式选择
- 支持笔记风格选择
- 支持多模态视频理解
- 支持多版本记录保留
- 支持自行配置 GPT 大模型（OpenAI、DeepSeek、Qwen 等）
- 本地模型音频转写（支持 Fast-Whisper、MLX-Whisper、Groq、BCut）
- GPT 大模型总结视频内容
- 自动生成结构化 Markdown 笔记
- 可选插入截图（自动截取）
- 可选内容跳转链接（关联原视频）
- 任务记录与历史回看
- 基于 RAG 的笔记内容 AI 问答（支持 Function Calling）
- 笔记顶部视频封面 Banner 展示
- 工作区和生成历史面板支持折叠/展开

### v2.0.0 新增

- 基于 RAG 的笔记内容 AI 问答功能，支持半屏/全屏模式
- AI 问答支持 Function Calling，模型可主动查询原文数据
- RAG 索引支持视频元信息（标题、作者、简介、标签等）
- AI 回复支持 Markdown 渲染
- 笔记顶部新增视频封面 Banner
- 工作区和生成历史面板支持折叠/展开
- 笔记开头添加来源链接功能
- YouTube 字幕优先获取，有字幕时跳过音频下载
- 性能优化与转写器配置改进

## 📸 截图预览
![screenshot](./doc/image1.png)
![screenshot](./doc/image3.png)
![screenshot](./doc/image.png)
![screenshot](./doc/image4.png)
![screenshot](./doc/image5.png)

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

确保已安装 Docker，直接拉取预构建镜像运行：

```bash
docker pull ghcr.io/jefferyhcool/bilinote:latest

docker run -d -p 80:80 \
  -v bilinote-data:/app/backend/data \
  --name bilinote \
  ghcr.io/jefferyhcool/bilinote:latest
```

访问：`http://localhost`

也可以使用 docker-compose 本地构建：

```bash
# 标准部署
docker-compose up -d

# GPU 加速部署（需要 NVIDIA GPU）
docker-compose -f docker-compose.gpu.yml up -d
```

### 方式二：源码部署

#### 1. 克隆仓库

```bash
git clone https://github.com/JefferyHcool/BiliNote.git
cd BiliNote
mv .env.example .env
```

#### 2. 启动后端（FastAPI）

```bash
cd backend
pip install -r requirements.txt
python main.py
```

#### 3. 启动前端（Vite + React）

```bash
cd BillNote_frontend
pnpm install
pnpm dev
```

访问：`http://localhost:3015`

## ⚙️ 依赖说明

### 🎬 FFmpeg
本项目依赖 ffmpeg 用于音频处理与转码，源码部署时必须安装：
```bash
# Mac (brew)
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
# 请从官网下载安装：https://ffmpeg.org/download.html
```
> ⚠️ 若系统无法识别 ffmpeg，请将其加入系统环境变量 PATH
>
> Docker 部署已内置 FFmpeg，无需额外安装。

### 🚀 CUDA 加速（可选）
若你希望更快地执行音频转写任务，可使用具备 NVIDIA GPU 的机器，并启用 fast-whisper + CUDA 加速版本：

具体 `fast-whisper` 配置方法，请参考：[fast-whisper 项目地址](http://github.com/SYSTRAN/faster-whisper#requirements)

### 🐳 使用 Docker 一键部署

确保你已安装 Docker，然后直接拉取预构建镜像运行：

```bash
# 拉取最新镜像
docker pull ghcr.io/jefferyhcool/bilinote:latest

# 运行容器
docker run -d -p 80:80 \
  -v bilinote-data:/app/backend/data \
  --name bilinote \
  ghcr.io/jefferyhcool/bilinote:latest
```

访问：`http://localhost`

也可以使用 docker-compose 本地构建：

```bash
# 标准部署
docker-compose up -d

# GPU 加速部署（需要 NVIDIA GPU）
docker-compose -f docker-compose.gpu.yml up -d
```

## 🧠 TODO

- [x] 支持抖音及快手等视频平台
- [x] 支持前端设置切换 AI 模型切换、语音转文字模型
- [x] AI 摘要风格自定义（学术风、口语风、重点提取等）
- [x] 加入更多模型支持
- [x] 加入更多音频转文本模型支持
- [x] 基于 RAG 的笔记内容 AI 问答
- [ ] 笔记导出为 PDF / Word / Notion

### Contact and Join-联系和加入社区
年会恢复更新以后放出最新社区地址



## 🔎代码参考
- 本项目中的 `抖音下载功能` 部分代码参考引用自：[Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API)

## 📜 License

MIT License

---

💬 你的支持与反馈是我持续优化的动力！欢迎 PR、提 issue、Star ⭐️
## Buy Me a Coffee / 捐赠
如果你觉得项目对你有帮助，考虑支持我一下吧
<div style='display:inline;'>
    <img width='30%' src='https://common-1304618721.cos.ap-chengdu.myqcloud.com/8986c9eb29c356a0cfa3d470c23d3b6.jpg'/>
    <img width='30%' src='https://common-1304618721.cos.ap-chengdu.myqcloud.com/2a049ea298b206bcd0d8b8da3219d6b.jpg'/>
</div>

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JefferyHcool/BiliNote&type=Date)](https://www.star-history.com/#JefferyHcool/BiliNote&Date)
