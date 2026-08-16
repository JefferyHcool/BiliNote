import { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback, memo, FC } from 'react'
import ReactMarkdown from 'react-markdown'
import { Button } from '@/components/ui/button.tsx'
import { AlertTriangle, Copy, ArrowRight, Play, ExternalLink, RotateCcw } from 'lucide-react'
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
import rehypeSlug from 'rehype-slug'
import 'katex/dist/katex.min.css'
import 'github-markdown-css/github-markdown-light.css'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { useTaskStore, type Task } from '@/store/taskStore'
import { noteStyles } from '@/constant/note.ts'
import { MarkdownHeader } from '@/pages/HomePage/components/MarkdownHeader.tsx'
import TranscriptViewer from '@/pages/HomePage/components/transcriptViewer.tsx'
import MarkmapEditor from '@/pages/HomePage/components/MarkmapComponent.tsx'
import ChatPanel from '@/pages/HomePage/components/ChatPanel.tsx'
import VideoBanner from '@/pages/HomePage/components/VideoBanner.tsx'
import MarkdownEditor from '@/pages/HomePage/components/MarkdownEditor.tsx'
import FloatingToc from '@/pages/HomePage/components/FloatingToc.tsx'
import { get_task_status } from '@/services/note.ts'

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

const remarkPlugins = [gfm, remarkMath]
const rehypePlugins = [rehypeKatex, rehypeSlug]

const extractPageFromUrl = (value?: string) => {
  const page = value?.match(/[?&]p=(\d+)/i)?.[1]
  return page ? Number(page) : undefined
}

const extractContentSourcePage = (content: string) => {
  const sourceUrl = content.match(/^>\s*来源链接：([^\n]+)/m)?.[1]
  return extractPageFromUrl(sourceUrl)
}

// 老版本批量任务没有 batch_page，因此同时从 URL、视频 ID 和标题推断分集。
const inferExpectedPage = (task?: Task | null) => {
  if (!task) return undefined
  if (task.formData.batch_page) return task.formData.batch_page

  const urlPage = extractPageFromUrl(task.formData.video_url)
  if (urlPage) return urlPage

  const videoIdPage = task.audioMeta?.video_id?.match(/(?:_|-)p(\d+)$/i)?.[1]
  if (videoIdPage) return Number(videoIdPage)

  const titlePage = task.audioMeta?.title?.match(/(?:^|[\s_-])P(\d+)(?=$|[\s_-])/i)?.[1]
  return titlePage ? Number(titlePage) : undefined
}

/**
 * 构建 ReactMarkdown components 对象，baseURL 用于修正图片路径。
 * 使用函数 + useMemo 避免每次渲染都创建新的函数实例。
 */
function createMarkdownComponents(baseURL: string) {
  return {
    h1: ({ children, ...props }: any) => (
      <h1
        className="text-primary my-6 scroll-m-20 text-3xl font-extrabold tracking-tight lg:text-4xl"
        {...props}
      >
        {children}
      </h1>
    ),
    h2: ({ children, ...props }: any) => (
      <h2
        className="text-primary mt-10 mb-4 scroll-m-20 border-b pb-2 text-2xl font-semibold tracking-tight first:mt-0"
        {...props}
      >
        {children}
      </h2>
    ),
    h3: ({ children, ...props }: any) => (
      <h3
        className="text-primary mt-8 mb-4 scroll-m-20 text-xl font-semibold tracking-tight"
        {...props}
      >
        {children}
      </h3>
    ),
    h4: ({ children, ...props }: any) => (
      <h4
        className="text-primary mt-6 mb-2 scroll-m-20 text-lg font-semibold tracking-tight"
        {...props}
      >
        {children}
      </h4>
    ),
    p: ({ children, ...props }: any) => (
      <p className="leading-7 [&:not(:first-child)]:mt-6" {...props}>
        {children}
      </p>
    ),
    a: ({ href, children, ...props }: any) => {
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

      // 处理笔记内部锚点链接（如目录跳转）
      if (href?.startsWith('#')) {
        const handleAnchorClick = (e: React.MouseEvent) => {
          e.preventDefault()
          const id = decodeURIComponent(href.slice(1))

          // 1. 优先精确匹配 id
          let target = document.getElementById(id)

          // 2. 精确失败时按 heading 文本模糊匹配
          // LLM 生成的目录锚点可能和 heading 实际文本不完全一致
          //（例如 heading 带 *Content-[00:00]* 后缀，目录链接里没有）
          if (!target) {
            const normalize = (s: string) =>
              s.replace(/[-：:\s*\[\]]/g, '').toLowerCase()
            const search = normalize(id)
            const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6')
            for (const h of headings) {
              const text = h.textContent || ''
              if (normalize(text).includes(search) || search.includes(normalize(text))) {
                target = h
                break
              }
            }
          }

          if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' })
          } else {
            toast.error('未找到对应章节')
          }
        }

        return (
          <a
            href={href}
            onClick={handleAnchorClick}
            className="text-primary hover:text-primary/80 inline-flex items-center gap-0.5 font-medium underline underline-offset-4"
            {...props}
          >
            {children}
          </a>
        )
      }

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
    img: ({ node, ...props }: any) => {
      let src = props.src
      if (src.startsWith('/')) {
        src = baseURL + src
      }
      props.src = src

      return (
        <div className="my-8 flex justify-center">
          <Zoom>
            <img
              {...props}
              className="max-w-full cursor-zoom-in rounded-lg object-cover shadow-md transition-all hover:shadow-lg"
              style={{ maxHeight: '500px' }}
            />
          </Zoom>
        </div>
      )
    },
    strong: ({ children, ...props }: any) => (
      <strong className="text-primary font-bold" {...props}>
        {children}
      </strong>
    ),
    li: ({ children, ...props }: any) => {
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
    ul: ({ children, ...props }: any) => (
      <ul className="my-6 ml-6 list-disc [&>li]:mt-2" {...props}>
        {children}
      </ul>
    ),
    ol: ({ children, ...props }: any) => (
      <ol className="my-6 ml-6 list-decimal [&>li]:mt-2" {...props}>
        {children}
      </ol>
    ),
    blockquote: ({ children, ...props }: any) => (
      <blockquote
        className="border-primary/20 text-muted-foreground mt-6 border-l-4 pl-4 italic"
        {...props}
      >
        {children}
      </blockquote>
    ),
    code: ({ inline, className, children, ...props }: any) => {
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

      return (
        <code
          className="bg-muted relative rounded px-[0.3rem] py-[0.2rem] font-mono text-sm"
          {...props}
        >
          {children}
        </code>
      )
    },
    table: ({ children, ...props }: any) => (
      <div className="my-6 w-full overflow-y-auto">
        <table className="w-full border-collapse text-sm" {...props}>
          {children}
        </table>
      </div>
    ),
    th: ({ children, ...props }: any) => (
      <th
        className="border-muted-foreground/20 border px-4 py-2 text-left font-medium [&[align=center]]:text-center [&[align=right]]:text-right"
        {...props}
      >
        {children}
      </th>
    ),
    td: ({ children, ...props }: any) => (
      <td
        className="border-muted-foreground/20 border px-4 py-2 text-left [&[align=center]]:text-center [&[align=right]]:text-right"
        {...props}
      >
        {children}
      </td>
    ),
    hr: ({ ...props }: any) => (
      <hr className="border-muted-foreground/20 my-8" {...props} />
    ),
  }
}

const MarkdownViewer: FC<MarkdownViewerProps> = memo(({ status }) => {
  const [currentVerId, setCurrentVerId] = useState<string>('')
  // 确保baseURL没有尾部斜杠
  const baseURL = (String(import.meta.env.VITE_API_BASE_URL || '').replace('/api','') || '').replace(/\/$/, '')
  const getCurrentTask = useTaskStore.getState().getCurrentTask
  const currentTask = useTaskStore(state => state.getCurrentTask())
  const taskStatus = currentTask?.status || 'PENDING'
  const retryTask = useTaskStore.getState().retryTask
  const isMultiVersion = Array.isArray(currentTask?.markdown)
  const [showTranscribe, setShowTranscribe] = useState(false)
  const [showChat, setShowChat] = useState<false | 'half' | 'full'>(false)
  const [viewMode, setViewMode] = useState<'map' | 'preview' | 'edit'>('preview')
  const updateTaskMarkdown = useTaskStore(state => state.updateTaskMarkdown)
  const markdownContentRef = useRef<HTMLDivElement>(null)
  const [floatingTocExpanded, setFloatingTocExpanded] = useState(false)
  const [restoringOriginal, setRestoringOriginal] = useState(false)
  const automaticRestoreAttempts = useRef(new Set<string>())

  // 缓存 ReactMarkdown components，仅在 baseURL 变化时重建
  const markdownComponents = useMemo(() => createMarkdownComponents(baseURL), [baseURL])

  // 直接从当前任务推导正文，绝不在任务切换时复用上一篇笔记的 selectedContent。
  // currentVerId 如果属于上一篇任务，会立刻回退到新任务的最新版本。
  const sortedVersions = useMemo(() => (
    Array.isArray(currentTask?.markdown)
      ? [...currentTask.markdown].sort(
        (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
      )
      : []
  ), [currentTask?.markdown])
  const latestVersion = sortedVersions[0]
  const selectedVersion = sortedVersions.find(version => version.ver_id === currentVerId)
    || latestVersion
  const effectiveVerId = selectedVersion?.ver_id || ''
  const selectedContent = typeof currentTask?.markdown === 'string'
    ? currentTask.markdown
    : selectedVersion?.content || ''
  const modelName = selectedVersion?.model_name || currentTask?.formData.model_name || ''
  const style = selectedVersion?.style || currentTask?.formData.style || ''
  const createTime = selectedVersion?.created_at || currentTask?.createdAt || ''
  const expectedBatchPage = inferExpectedPage(currentTask)
  const contentSourcePage = extractContentSourcePage(selectedContent)
  const batchPageMismatch = Boolean(
    expectedBatchPage
    && contentSourcePage
    && expectedBatchPage !== contentSourcePage,
  )

  useEffect(() => {
    setCurrentVerId(latestVersion?.ver_id || '')
    setViewMode('preview')
    setShowChat(false)
    setShowTranscribe(false)
  }, [currentTask?.id, latestVersion?.ver_id, taskStatus])

  useLayoutEffect(() => {
    if (viewMode !== 'preview') return
    const viewport = markdownContentRef.current
      ?.closest('[data-slot="scroll-area"]')
      ?.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')
    viewport?.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [currentTask?.id, effectiveVerId, taskStatus, viewMode])
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(selectedContent)
      toast.success('已复制到剪贴板')
    } catch {
      toast.error('复制失败')
    }
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

  const handleSaveEdit = (taskId: string, versionId: string, content: string) => {
    const stillCurrent = useTaskStore.getState().currentTaskId === taskId
    if (!stillCurrent) {
      toast.error('当前笔记已切换，已阻止将内容保存到其他笔记')
      return false
    }
    const saved = updateTaskMarkdown(taskId, content, versionId || undefined)
    if (saved) {
      setViewMode('preview')
    }
    return saved
  }

  const loadOriginalGeneratedContent = async (taskId: string) => {
    const response = await get_task_status(taskId)
    if (response?.status !== 'SUCCESS' || typeof response?.result?.markdown !== 'string') {
      return null
    }
    return response.result.markdown as string
  }

  const restoreOriginalContent = useCallback(async (askForConfirmation: boolean) => {
    if (!currentTask || !batchPageMismatch) return
    if (askForConfirmation && !window.confirm(
      `当前是 P${expectedBatchPage}，但正文来源是 P${contentSourcePage}。是否从后端缓存恢复 P${expectedBatchPage} 的原始生成稿？`,
    )) return

    const taskId = currentTask.id
    const versionId = effectiveVerId
    setRestoringOriginal(true)
    try {
      const original = await loadOriginalGeneratedContent(taskId)
      const originalPage = original ? extractContentSourcePage(original) : undefined
      if (!original || (originalPage && originalPage !== expectedBatchPage)) {
        toast.error('后端原始生成稿与当前分集不匹配，已停止恢复')
        return
      }
      if (useTaskStore.getState().currentTaskId !== taskId) return
      if (!updateTaskMarkdown(taskId, original, versionId || undefined)) {
        toast.error('恢复失败，当前任务或版本已变化')
        return
      }
      toast.success(`P${expectedBatchPage} 原始生成稿已恢复，覆盖前内容已自动备份`)
    } catch {
      toast.error('读取后端原始生成稿失败')
    } finally {
      setRestoringOriginal(false)
    }
  }, [batchPageMismatch, contentSourcePage, currentTask, effectiveVerId, expectedBatchPage, updateTaskMarkdown])

  const restoreOriginalImmediately = () => restoreOriginalContent(true)

  useEffect(() => {
    if (!currentTask || !batchPageMismatch) return
    const attemptKey = `${currentTask.id}:${effectiveVerId || 'legacy'}`
    if (automaticRestoreAttempts.current.has(attemptKey)) return
    automaticRestoreAttempts.current.add(attemptKey)
    void restoreOriginalContent(false)
  }, [batchPageMismatch, currentTask, effectiveVerId, restoreOriginalContent])

  const renderMarkdown = (content: string) => (
    <ReactMarkdown
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={markdownComponents}
    >
      {content.replace(/^>\s*来源链接：[^\n]*\n*/m, '')}
    </ReactMarkdown>
  )

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
          <p className="text-lg font-bold">输入视频链接并点击"生成笔记"</p>
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
      {viewMode !== 'edit' && (
        <MarkdownHeader
          currentTask={currentTask}
          isMultiVersion={isMultiVersion}
          currentVerId={effectiveVerId}
          setCurrentVerId={setCurrentVerId}
          modelName={modelName}
          style={style}
          noteStyles={noteStyles}
          onCopy={handleCopy}
          onDownload={handleDownload}
          createAt={createTime}
          showTranscribe={showTranscribe}
          setShowTranscribe={setShowTranscribe}
          showChat={showChat}
          setShowChat={setShowChat}
          viewMode={viewMode}
          setViewMode={setViewMode}
        />
      )}

      {viewMode === 'edit' && currentTask ? (
        <MarkdownEditor
          key={`${currentTask.id}-${effectiveVerId || 'legacy'}`}
          value={selectedContent}
          onSave={content => handleSaveEdit(currentTask.id, effectiveVerId, content)}
          onCancel={() => setViewMode('preview')}
          renderPreview={renderMarkdown}
          onRestoreOriginal={
            !selectedVersion || selectedVersion.ver_id === latestVersion?.ver_id
              ? () => loadOriginalGeneratedContent(currentTask.id)
              : undefined
          }
        />
      ) : viewMode === 'map' ? (
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
              {showChat === 'full' && currentTask ? (
                <div className="h-full w-full">
                  <ChatPanel taskId={currentTask.id} mode="full" onModeChange={setShowChat} />
                </div>
              ) : (
              <>
              <div className="relative min-w-0 flex-1">
                <ScrollArea className="h-full w-full">
                  {batchPageMismatch && (
                    <div className="mx-2 mb-2 flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 flex-1">
                        检测到当前任务是 P{expectedBatchPage}，但正文来源是 P{contentSourcePage}。
                      </span>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={restoringOriginal}
                        onClick={restoreOriginalImmediately}
                      >
                        <RotateCcw className="h-4 w-4" />
                        {restoringOriginal ? '恢复中…' : '恢复正确原稿'}
                      </Button>
                    </div>
                  )}
                  <div className="px-2">
                    <VideoBanner
                      audioMeta={currentTask?.audioMeta}
                      videoUrl={currentTask?.formData?.video_url}
                    />
                  </div>
                  <div
                    ref={markdownContentRef}
                    className={`markdown-body w-full py-0 pl-2 transition-[padding] duration-200 ${
                      floatingTocExpanded ? 'pr-[13rem] xl:pr-[15rem]' : 'pr-2'
                    }`}
                  >
                    {renderMarkdown(selectedContent)}
                  </div>
                </ScrollArea>
                <FloatingToc
                  contentRootRef={markdownContentRef}
                  contentKey={`${currentTask?.id || ''}-${effectiveVerId}-${selectedContent}`}
                  onExpandedChange={setFloatingTocExpanded}
                />
              </div>
              {showTranscribe && (
                <div className={'ml-2 w-2/4'}>
                  <TranscriptViewer />
                </div>
              )}
              {/* 侧边问答模式：markdown + ChatPanel 各占一半 */}
              {showChat === 'half' && currentTask && (
                <div className="ml-2 h-full w-1/2 shrink-0">
                  <ChatPanel taskId={currentTask.id} mode="half" onModeChange={setShowChat} />
                </div>
              )}
              </>
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
})

MarkdownViewer.displayName = 'MarkdownViewer'

export default MarkdownViewer
