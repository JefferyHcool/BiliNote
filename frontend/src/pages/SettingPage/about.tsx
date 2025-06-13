import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Github, Star, ExternalLink, Download } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import logo from '@/assets/icon.svg'

export default function AboutPage() {
  const images = [
    'https://common-1304618721.cos.ap-chengdu.myqcloud.com/20250504102850.png',
    'https://common-1304618721.cos.ap-chengdu.myqcloud.com/20250504103028.png',
    'https://common-1304618721.cos.ap-chengdu.myqcloud.com/20250504103304.png',
    'https://common-1304618721.cos.ap-chengdu.myqcloud.com/20250504103625.png',
  ]
  return (
    <ScrollArea className={'h-full overflow-y-auto bg-white'}>
      <div className="container mx-auto px-4 py-12">
        {/* Hero Section */}
        <div className="mb-16 flex flex-col items-center justify-center text-center">
          <div className="mb-4 flex items-center gap-4">
            <img
              src={logo}
              alt="BiliNote Logo"
              width={50}
              height={50}
              className="rounded-lg"
            />
            <h1 className="text-4xl font-bold">BiliNote v1.7.5</h1>
          </div>
          <p className="text-muted-foreground mb-6 text-xl italic">
            AI 视频笔记生成工具 让 AI 为你的视频做笔记
          </p>

          <div className="mb-8 flex flex-wrap justify-center gap-2">
            <Badge variant="secondary">MIT License</Badge>
            <Badge variant="secondary">React</Badge>
            <Badge variant="secondary">FastAPI</Badge>
            <Badge variant="secondary">Docker Compose</Badge>
            <Badge variant="secondary">Active</Badge>
          </div>

          <div className="flex flex-wrap justify-center gap-4">
            <Button asChild>
              <a href="https://www.bilinote.app" target="_blank">
                <ExternalLink className="mr-2 h-4 w-4" />
                体验 BiliNote
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href="https://github.com/JefferyHcool/BiliNote" target="_blank">
                <Github className="mr-2 h-4 w-4" />
                GitHub 仓库
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href="https://github.com/JefferyHcool/BiliNote/releases" target="_blank">
                <Download className="mr-2 h-4 w-4" />
                下载桌面版
              </a>
            </Button>
          </div>
        </div>

        {/* Project Introduction */}
        <section className="mb-16">
          <h2 className="mb-6 text-center text-3xl font-bold">✨ 项目简介</h2>
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-lg">
              BiliNote 是一个开源的 AI 视频笔记助手，支持通过哔哩哔哩、YouTube、抖音等视频链接，
              自动提取内容并生成结构清晰、重点明确的 Markdown
              格式笔记。支持插入截图、原片跳转等功能。
            </p>
          </div>
        </section>

        {/* Features Section */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold">🔧 功能特性</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[
              { title: '多平台支持', desc: '支持 Bilibili、YouTube、本地视频、抖音等多个平台' },
              { title: '笔记格式选择', desc: '支持返回多种笔记格式，满足不同需求' },
              { title: '笔记风格选择', desc: '支持多种笔记风格，个性化定制' },
              { title: '多模态视频理解', desc: '结合视觉和音频内容，全面理解视频' },
              { title: '自定义 GPT 配置', desc: '支持自行配置 GPT 大模型' },
              { title: '本地音频转写', desc: '支持 Fast-Whisper 等本地模型音频转写' },
              { title: '结构化笔记', desc: '自动生成结构化 Markdown 笔记' },
              { title: '智能截图', desc: '可选插入自动截取的关键画面' },
              { title: '内容跳转', desc: '支持关联原视频的内容跳转链接' },
            ].map((feature, index) => (
              <Card key={index} className="h-full">
                <CardContent className="pt-2">
                  <h3 className="mb-2 text-xl font-semibold">{feature.title}</h3>
                  <p className="text-muted-foreground">{feature.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Screenshots Section */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold">📸 截图预览</h2>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {images.map(num => (
              <div key={num} className="overflow-hidden rounded-lg border shadow-sm">
                <img
                  src={num}
                  alt={`BiliNote Screenshot ${num}`}
                  width={600}
                  height={400}
                  className="w-full object-cover transition-transform hover:scale-105"
                />
              </div>
            ))}
          </div>
        </section>

        {/* Quick Start Section */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold">🚀 快速开始</h2>
          <Tabs defaultValue="manual" className="mx-auto max-w-3xl">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="manual">手动安装</TabsTrigger>
              <TabsTrigger value="docker">Docker 部署</TabsTrigger>
            </TabsList>
            <TabsContent value="manual" className="mt-6 space-y-6">
              <div>
                <h3 className="mb-3 text-xl font-semibold">1. 克隆仓库</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  git clone https://github.com/JefferyHcool/BiliNote.git
                  <br />
                  cd BiliNote
                  <br />
                  mv .env.example .env
                </div>
              </div>
              <div>
                <h3 className="mb-3 text-xl font-semibold">2. 启动后端（FastAPI）</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  cd backend
                  <br />
                  pip install -r requirements.txt
                  <br />
                  python main.py
                </div>
              </div>
              <div>
                <h3 className="mb-3 text-xl font-semibold">3. 启动前端（Vite + React）</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  cd BiliNote_frontend
                  <br />
                  pnpm install
                  <br />
                  pnpm dev
                </div>
              </div>
              <p>
                访问：<code className="bg-muted rounded px-2 py-1">http://localhost:5173</code>
              </p>
            </TabsContent>
            <TabsContent value="docker" className="mt-6 space-y-6">
              <div>
                <h3 className="mb-3 text-xl font-semibold">1. 克隆仓库</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  git clone https://github.com/JefferyHcool/BiliNote.git
                  <br />
                  cd BiliNote
                  <br />
                  mv .env.example .env
                </div>
              </div>
              <div>
                <h3 className="mb-3 text-xl font-semibold">2. 启动 Docker Compose</h3>
                <div className="bg-muted rounded-md p-4 font-mono text-sm">
                  docker compose up --build
                </div>
              </div>
              <p>
                默认端口：
                <br />
                前端：http://localhost:${'{FRONTEND_PORT}'}
                <br />
                后端：http://localhost:${'{BACKEND_PORT}'}
                <br />
                <span className="text-muted-foreground text-sm">
                  .env 文件中可自定义端口与环境配置
                </span>
              </p>
            </TabsContent>
          </Tabs>
        </section>

        {/* Community Section */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold">联系和加入社区</h2>
          <div className="mx-auto max-w-3xl">
            <div className="flex flex-col items-center justify-center gap-8">
              <div className="text-center">
                <h3 className="mb-3 text-xl font-semibold">BiliNote 交流 QQ 群</h3>
                <p className="text-lg font-medium">785367111</p>
              </div>
              <div className="text-center">
                <h3 className="mb-3 text-xl font-semibold">BiliNote 交流微信群</h3>
                <div className="bg-muted mx-auto flex h-52 w-52 items-center justify-center rounded-md">
                  <img src={'https://common-1304618721.cos.ap-chengdu.myqcloud.com/wechat.png'} />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* License Section */}
        <section className="mb-8 text-center">
          <h2 className="mb-4 text-3xl font-bold">📜 License</h2>
          <p>MIT License</p>
        </section>

        {/* Footer */}
        <footer className="border-t pt-8 text-center">
          <p className="mb-4">💬 你的支持与反馈是我持续优化的动力！欢迎 PR、提 issue、Star ⭐️</p>
        </footer>
      </div>
    </ScrollArea>
  )
}
