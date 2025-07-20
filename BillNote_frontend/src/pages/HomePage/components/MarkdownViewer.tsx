import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { Button } from '@/components/ui/button.tsx'
import { Copy, Download, ArrowRight, Play, ExternalLink } from 'lucide-react'
import { toast } from 'react-hot-toast'
import Error from '@/components/Lottie/error.tsx'
import Loading from '@/components/Lottie/Loading.tsx'
import Idle from '@/components/Lottie/Idle.tsx'
import StepBar from '@/pages/HomePage/components/StepBar.tsx'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { atomDark as codeStyle } from 'react-syntax-highlighter/dist/esm/styles/prism'
import Zoom from 'react-medium-image-zoom'
import 'react-medium-image-zoom/dist/styles.css'
import gfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import 'github-markdown-css/github-markdown-light.css'
import { FC } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { useTaskStore } from '@/store/taskStore'
import { noteStyles } from '@/constant/note.ts'
import { MarkdownHeader } from '@/pages/HomePage/components/MarkdownHeader.tsx'
import TranscriptViewer from '@/pages/HomePage/components/transcriptViewer.tsx'
import MarkmapEditor from '@/pages/HomePage/components/MarkmapComponent.tsx'

interface VersionNote {
  ver_id: string
  content: string
  style: string
  model_name: string
  created_at?: string
}

interface MarkdownViewerProps {
  content: string | VersionNote[]
  status: 'idle' | 'loading' | 'success' | 'failed'
}

const steps = [
  { label: '解析链接', key: 'PARSING' },
  { label: '下载音频', key: 'DOWNLOADING' },
  { label: '转写文字', key: 'TRANSCRIBING' },
  { label: '总结内容', key: 'SUMMARIZING' },
  { label: '保存完成', key: 'SUCCESS' },
]

const MarkdownViewer: FC<MarkdownViewerProps> = ({ status }) => {
  const [copied, setCopied] = useState(false)
  const [currentVerId, setCurrentVerId] = useState<string>('')
  const [selectedContent, setSelectedContent] = useState<string>('')
  const [modelName, setModelName] = useState<string>('')
  const [style, setStyle] = useState<string>('')
  const [createTime, setCreateTime] = useState<string>('')
  const baseURL = String(import.meta.env.VITE_API_BASE_URL).replace('/api','') || ''
  const getCurrentTask = useTaskStore.getState().getCurrentTask
  const currentTask = useTaskStore(state => state.getCurrentTask())
  const taskStatus = currentTask?.status || 'PENDING'
  const retryTask = useTaskStore.getState().retryTask
  const isMultiVersion = Array.isArray(currentTask?.markdown)
  const [showTranscribe, setShowTranscribe] = useState(false)
  const [viewMode, setViewMode] = useState<'map' | 'preview'>('preview')
  const svgRef = useRef<SVGSVGElement>(null)
  // 多版本内容处理
  useEffect(() => {
    if (!currentTask) return

    if (!isMultiVersion) {
      setCurrentVerId('') // 清空旧版本 ID
      setModelName(currentTask.formData.model_name)
      setStyle(currentTask.formData.style)
      setCreateTime(currentTask.createdAt)
      setSelectedContent(currentTask?.markdown)
    } else {
      const latestVersion = [...currentTask.markdown].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )[0]

      if (latestVersion) {
        setCurrentVerId(latestVersion.ver_id)
      }
    }
  }, [currentTask?.id, taskStatus])
  useEffect(() => {
    if (!currentTask || !isMultiVersion) return

    const currentVer = currentTask.markdown.find(v => v.ver_id === currentVerId)
    if (currentVer) {
      setModelName(currentVer.model_name)
      setStyle(currentVer.style)
      setCreateTime(currentVer.created_at || '')
      setSelectedContent(currentVer.content)
    }
  }, [currentVerId, currentTask?.id])
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(selectedContent)
      setCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      toast.error('复制失败')
    }
  }
  const alertButton = {
    id: 'alert',
    title: '测试警告',
    content: '⚠️',
    onClick: () => alert('你点击了自定义按钮！'),
  }
  const exportButton = {
    id: 'export',
    title: '导出思维导图',
    content: '⤓',
    onClick: () => {
      const svgEl = svgRef.current
      if (!svgEl) return
      // 同上面的序列化逻辑
      const serializer = new XMLSerializer()
      const source = serializer.serializeToString(svgEl)
      const blob = new Blob(['<?xml version="1.0" encoding="UTF-8"?>', source], {
        type: 'image/svg+xml;charset=utf-8',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'mindmap.svg'
      a.click()
      URL.revokeObjectURL(url)
    },
  }
  const handleDownload = () => {
    const task = getCurrentTask()
    const name = task?.audioMeta.title || 'note'
    const blob = new Blob([selectedContent], { type: 'text/markdown;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${name}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  if (status === 'loading') {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center space-y-4 text-neutral-500">
        <StepBar steps={steps} currentStep={taskStatus} />
        <Loading className="h-5 w-5" />
        <div className="text-center text-sm">
          <p className="text-lg font-bold">正在生成笔记，请稍候…</p>
          <p className="mt-2 text-xs text-neutral-500">这可能需要几秒钟时间，取决于视频长度</p>
        </div>
      </div>
    )
  }

  if (status === 'idle') {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center space-y-3 text-neutral-500">
        <Idle />
        <div className="text-center">
          <p className="text-lg font-bold">输入视频链接并点击“生成笔记”</p>
          <p className="mt-2 text-xs text-neutral-500">支持哔哩哔哩、YouTube 、抖音等视频平台</p>
        </div>
      </div>
    )
  }

  if (status === 'failed' && !isMultiVersion) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center gap-4 space-y-3">
        <Error />
        <div className="text-center">
          <p className="text-lg font-bold text-red-500">笔记生成失败</p>
          <p className="mt-2 mb-2 text-xs text-red-400">请检查后台或稍后再试</p>

          <Button onClick={() => retryTask(currentTask.id)} size="lg">
            重试
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      <MarkdownHeader
        currentTask={currentTask}
        isMultiVersion={isMultiVersion}
        currentVerId={currentVerId}
        setCurrentVerId={setCurrentVerId}
        modelName={modelName}
        style={style}
        noteStyles={noteStyles}
        onCopy={handleCopy}
        onDownload={handleDownload}
        createAt={createTime}
        showTranscribe={showTranscribe}
        setShowTranscribe={setShowTranscribe}
        viewMode={viewMode}
        setViewMode={setViewMode}
      />

      {viewMode === 'map' ? (
        <div className="flex w-full flex-1 overflow-hidden bg-white">
          <div className={'w-full'}>
            <MarkmapEditor
              value={selectedContent}
              onChange={() => {}}
              height="100%" // 根据需求可以设定百分比或固定高度
              title={currentTask?.audioMeta?.title || '思维导图'}
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden bg-white py-2">
          {selectedContent && selectedContent !== 'loading' && selectedContent !== 'empty' ? (
            <>
              <ScrollArea className="w-full">
                <div className={'markdown-body w-full px-2'}>
                  <ReactMarkdown
                    remarkPlugins={[gfm, remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                    components={{
                      // Headings with improved styling and anchor links
                      h1: ({ children, ...props }) => (
                        <h1
                          className="text-primary my-6 scroll-m-20 text-3xl font-extrabold tracking-tight lg:text-4xl"
                          {...props}
                        >
                          {children}
                        </h1>
                      ),
                      h2: ({ children, ...props }) => (
                        <h2
                          className="text-primary mt-10 mb-4 scroll-m-20 border-b pb-2 text-2xl font-semibold tracking-tight first:mt-0"
                          {...props}
                        >
                          {children}
                        </h2>
                      ),
                      h3: ({ children, ...props }) => (
                        <h3
                          className="text-primary mt-8 mb-4 scroll-m-20 text-xl font-semibold tracking-tight"
                          {...props}
                        >
                          {children}
                        </h3>
                      ),
                      h4: ({ children, ...props }) => (
                        <h4
                          className="text-primary mt-6 mb-2 scroll-m-20 text-lg font-semibold tracking-tight"
                          {...props}
                        >
                          {children}
                        </h4>
                      ),

                      // Paragraphs with better line height
                      p: ({ children, ...props }) => (
                        <p className="leading-7 [&:not(:first-child)]:mt-6" {...props}>
                          {children}
                        </p>
                      ),

                      // Enhanced links with special handling for "原片" links
                      a: ({ href, children, ...props }) => {
                        const isOriginLink =
                          typeof children[0] === 'string' &&
                          (children[0] as string).startsWith('原片 @')

                        if (isOriginLink) {
                          const timeMatch = (children[0] as string).match(/原片 @ (\d{2}:\d{2})/)
                          const timeText = timeMatch ? timeMatch[1] : '原片'

                          return (
                            <span className="origin-link my-2 inline-flex">
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100"
                                {...props}
                              >
                                <Play className="h-3.5 w-3.5" />
                                <span>原片（{timeText}）</span>
                              </a>
                            </span>
                          )
                        }

                        // Default link styling with external indicator
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:text-primary/80 inline-flex items-center gap-0.5 font-medium underline underline-offset-4"
                            {...props}
                          >
                            {children}
                            {href?.startsWith('http') && (
                              <ExternalLink className="ml-0.5 inline-block h-3 w-3" />
                            )}
                          </a>
                        )
                      },

                      // Enhanced image with zoom capability
                      img: ({ node, ...props }) =>{

                        let src = baseURL +props.src
                        props.src = src


                     return(


                      <div className="my-8 flex justify-center">
                          <Zoom>
                            <img
                              {...props}
                              className="max-w-full cursor-zoom-in rounded-lg object-cover shadow-md transition-all hover:shadow-lg"
                              style={{ maxHeight: '500px' }}
                            />
                          </Zoom>
                        </div>
                      )},

                      // Better strong/bold text
                      strong: ({ children, ...props }) => (
                        <strong className="text-primary font-bold" {...props}>
                          {children}
                        </strong>
                      ),

                      // Enhanced list items with support for "fake headings"
                      li: ({ children, ...props }) => {
                        const rawText = String(children)
                        const isFakeHeading = /^(\*\*.+\*\*)$/.test(rawText.trim())

                        if (isFakeHeading) {
                          return (
                            <div className="text-primary my-4 text-lg font-bold">{children}</div>
                          )
                        }

                        return (
                          <li className="my-1" {...props}>
                            {children}
                          </li>
                        )
                      },

                      // Enhanced unordered lists
                      ul: ({ children, ...props }) => (
                        <ul className="my-6 ml-6 list-disc [&>li]:mt-2" {...props}>
                          {children}
                        </ul>
                      ),

                      // Enhanced ordered lists
                      ol: ({ children, ...props }) => (
                        <ol className="my-6 ml-6 list-decimal [&>li]:mt-2" {...props}>
                          {children}
                        </ol>
                      ),

                      // Enhanced blockquotes
                      blockquote: ({ children, ...props }) => (
                        <blockquote
                          className="border-primary/20 text-muted-foreground mt-6 border-l-4 pl-4 italic"
                          {...props}
                        >
                          {children}
                        </blockquote>
                      ),

                      // Enhanced code blocks with syntax highlighting and copy button
                      code: ({ inline, className, children, ...props }) => {
                        const match = /language-(\w+)/.exec(className || '')
                        const codeContent = String(children).replace(/\n$/, '')

                        if (!inline && match) {
                          return (
                            <div className="group bg-muted relative my-6 overflow-hidden rounded-lg border shadow-sm">
                              <div className="bg-muted text-muted-foreground flex items-center justify-between px-4 py-1.5 text-sm font-medium">
                                <div>{match[1].toUpperCase()}</div>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(codeContent)
                                    toast.success('代码已复制')
                                  }}
                                  className="bg-background/80 hover:bg-background flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors"
                                >
                                  <Copy className="h-3.5 w-3.5" />
                                  复制
                                </button>
                              </div>
                              <SyntaxHighlighter
                                style={codeStyle}
                                language={match[1]}
                                PreTag="div"
                                className="!bg-muted !m-0 !p-0"
                                customStyle={{
                                  margin: 0,
                                  padding: '1rem',
                                  background: 'transparent',
                                  fontSize: '0.9rem',
                                }}
                                {...props}
                              >
                                {codeContent}
                              </SyntaxHighlighter>
                            </div>
                          )
                        }

                        // Inline code styling
                        return (
                          <code
                            className="bg-muted relative rounded px-[0.3rem] py-[0.2rem] font-mono text-sm"
                            {...props}
                          >
                            {children}
                          </code>
                        )
                      },

                      // Enhanced tables
                      table: ({ children, ...props }) => (
                        <div className="my-6 w-full overflow-y-auto">
                          <table className="w-full border-collapse text-sm" {...props}>
                            {children}
                          </table>
                        </div>
                      ),

                      // Table headers
                      th: ({ children, ...props }) => (
                        <th
                          className="border-muted-foreground/20 border px-4 py-2 text-left font-medium [&[align=center]]:text-center [&[align=right]]:text-right"
                          {...props}
                        >
                          {children}
                        </th>
                      ),

                      // Table cells
                      td: ({ children, ...props }) => (
                        <td
                          className="border-muted-foreground/20 border px-4 py-2 text-left [&[align=center]]:text-center [&[align=right]]:text-right"
                          {...props}
                        >
                          {children}
                        </td>
                      ),

                      // Horizontal rule
                      hr: ({ ...props }) => (
                        <hr className="border-muted-foreground/20 my-8" {...props} />
                      ),
                    }}
                  >
                    {selectedContent}
                  </ReactMarkdown>
                </div>
              </ScrollArea>
              {showTranscribe && (
                <div className={'ml-2 w-2/4'}>
                  <TranscriptViewer />
                </div>
              )}
            </>
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <div className="w-[300px] flex-col justify-items-center">
                <div className="bg-primary-light mb-4 flex h-16 w-16 items-center justify-center rounded-full">
                  <ArrowRight className="text-primary h-8 w-8" />
                </div>
                <p className="mb-2 text-neutral-600">输入视频链接并点击"生成笔记"按钮</p>
                <p className="text-xs text-neutral-500">支持哔哩哔哩、YouTube等视频网站</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default MarkdownViewer
