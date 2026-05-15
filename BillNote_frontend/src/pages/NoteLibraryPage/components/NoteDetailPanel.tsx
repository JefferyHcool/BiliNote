import { useState, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import 'github-markdown-css/github-markdown-light.css'
import Zoom from 'react-medium-image-zoom'
import 'react-medium-image-zoom/dist/styles.css'
import { Copy, Download, Trash2, BookOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger,
} from '@/components/ui/select'
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'
import { useTaskStore, type Markdown } from '@/store/taskStore'
import { get_task_status, normalizeDownloadQuality, normalizeGridSize, normalizeVideoInterval } from '@/services/note'
import { noteStyles } from '@/constant/note'

const remarkPlugins = [remarkGfm, remarkMath]
const rehypePlugins = [rehypeKatex]

function buildMarkdownComponents(baseURL: string) {
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    img: ({ src: rawSrc, ...props }: any) => {
      let src = rawSrc || ''
      if (src.startsWith('/')) src = baseURL + src
      return (
        <div className="my-6 flex justify-center">
          <Zoom>
            <img {...props} src={src} className="max-w-full rounded-md shadow-sm" />
          </Zoom>
        </div>
      )
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    pre: ({ children, ...props }: any) => (
      <pre className="overflow-x-auto rounded-md bg-neutral-900 p-4 text-sm text-neutral-100" {...props}>
        {children}
      </pre>
    ),
  }
}

function downloadMarkdown(content: string, title: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title || 'note'}.md`
  a.click()
  URL.revokeObjectURL(url)
}

interface NoteDetailPanelProps {
  noteId: string | null
  onDelete: (id: string) => void
}

export function NoteDetailPanel({ noteId, onDelete }: NoteDetailPanelProps) {
  // 与 MarkdownViewer 保持一致：去掉 /api 后缀，再去尾部斜杠
  const baseURL = (String(import.meta.env.VITE_API_BASE_URL || '').replace('/api', '') || '').replace(/\/$/, '')
  const markdownComponents = useMemo(() => buildMarkdownComponents(baseURL), [baseURL])

  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)
  const deleteNoteVersion = useTaskStore(state => state.deleteNoteVersion)

  const task = noteId ? tasks.find(t => t.id === noteId) ?? null : null

  const [selectedContent, setSelectedContent] = useState('')
  const [currentVerId, setCurrentVerId] = useState('')
  const [modelName, setModelName] = useState('')
  const [style, setStyle] = useState('')
  const [showTranscript, setShowTranscript] = useState(false)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const prevNoteIdRef = useRef<string | null>(null)

  const isMultiVersion = Array.isArray(task?.markdown)
  const versions: Markdown[] = isMultiVersion ? (task!.markdown as Markdown[]) : []
  const styleName = noteStyles.find(s => s.value === style)?.label || style

  // Reset on note change
  useLayoutEffect(() => {
    if (prevNoteIdRef.current !== noteId) {
      prevNoteIdRef.current = noteId
      setSelectedContent('')
      setCurrentVerId('')
      setModelName('')
      setStyle('')
      setShowTranscript(false)
    }
  }, [noteId])

  // Lazy-fetch markdown if the task is SUCCESS but has no markdown in store
  useEffect(() => {
    if (!task || task.status !== 'SUCCESS') return
    const hasContent = isMultiVersion ? versions.length > 0 : !!task.markdown
    if (hasContent) return

    let cancelled = false
    setLoading(true)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    get_task_status(task.id, { includeTranscript: false }).then((res: any) => {
        if (cancelled) return
        const result = res?.result
        if (!result) return
        const markdownPayload: string | Markdown[] =
          Array.isArray(result.markdown_versions) && result.markdown_versions.length > 0
            ? result.markdown_versions as Markdown[]
            : result.markdown
        const audioMeta = result.audio_meta ?? task.audioMeta
        const gp = result.generation_params ?? {}
        const fallbackUrl =
          audioMeta?.raw_info?.webpage_url || audioMeta?.raw_info?.original_url || ''
        updateTaskContent(task.id, {
          markdown: markdownPayload,
          audioMeta,
          formData: {
            ...task.formData,
            video_url:           task.formData?.video_url           || gp.video_url       || fallbackUrl,
            platform:            task.formData?.platform            || gp.platform        || audioMeta?.platform || '',
            model_name:          task.formData?.model_name          || gp.model_name      || '',
            provider_id:         task.formData?.provider_id         || gp.provider_id     || '',
            style:               task.formData?.style               || gp.style           || '',
            quality:             normalizeDownloadQuality(task.formData?.quality || gp.quality),
            extras:              task.formData?.extras              || gp.extras          || '',
            link:                task.formData?.link                ?? gp.link            ?? false,
            screenshot:          task.formData?.screenshot          ?? gp.screenshot      ?? false,
            video_understanding: task.formData?.video_understanding ?? gp.video_understanding ?? false,
            video_interval:      normalizeVideoInterval(task.formData?.video_interval ?? gp.video_interval),
            grid_size:           normalizeGridSize(task.formData?.grid_size ?? gp.grid_size),
          },
        })
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
    // task object ref intentionally excluded; we only re-run on id/status change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.id, task?.status, isMultiVersion, versions.length])

  // Sync content when task/version changes
  useEffect(() => {
    if (!task) return

    if (!isMultiVersion) {
      setSelectedContent(typeof task.markdown === 'string' ? task.markdown : '')
      setModelName(task.formData?.model_name ?? '')
      setStyle(task.formData?.style ?? '')
      return
    }

    const sorted = [...versions].sort(
      (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
    )
    const target = currentVerId
      ? versions.find(v => v.ver_id === currentVerId) ?? sorted[0]
      : sorted[0]

    if (target) {
      setCurrentVerId(target.ver_id)
      setSelectedContent(target.content)
      setModelName(target.model_name)
      setStyle(target.style)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.id, task?.markdown, currentVerId, isMultiVersion])

  // Lazy-fetch transcript
  useEffect(() => {
    if (!showTranscript || !task) return
    const hasTranscript = !!task.transcript?.full_text || (task.transcript?.segments?.length ?? 0) > 0
    if (hasTranscript) return

    let cancelled = false
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    get_task_status(task.id).then((res: any) => {
      if (cancelled) return
      const transcript = res?.result?.transcript
      if (transcript) updateTaskContent(task.id, { transcript })
    }).catch(() => {})
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showTranscript, task?.id])

  const handleCopy = () => {
    if (!selectedContent) return
    navigator.clipboard.writeText(selectedContent).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleDownload = () => {
    if (!selectedContent) return
    downloadMarkdown(selectedContent, task?.audioMeta?.title || 'note')
  }

  const handleDeleteVersion = async (verId: string) => {
    if (!task) return
    if (versions.length <= 1) return
    await deleteNoteVersion(task.id, verId)
  }

  // Empty / loading states
  if (!noteId) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-400">
        <BookOpen className="h-12 w-12 opacity-30" />
        <p className="text-sm">选择左侧笔记查看详情</p>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">笔记不存在</div>
    )
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">加载中…</div>
    )
  }

  if (!selectedContent) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        {task.status === 'SUCCESS' ? '正在获取笔记内容…' : `任务状态：${task.status}`}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* 顶部：版本选择 + 元信息 + 操作按钮 */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-white/95 px-4 py-2 backdrop-blur-sm">
        {/* 左：版本 + 标签 */}
        <div className="flex flex-wrap items-center gap-2">
          {versions.length > 1 && (
            <div className="flex items-center gap-1">
              <Select value={currentVerId} onValueChange={setCurrentVerId}>
                <SelectTrigger className="h-7 w-[150px] text-xs">
                  <div className="truncate">版本（{currentVerId.slice(-6)}）</div>
                </SelectTrigger>
                <SelectContent>
                  {versions.map(v => (
                    <SelectItem key={v.ver_id} value={v.ver_id} className="text-xs">
                      版本（{v.ver_id.slice(-6)}）
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {versions.length > 1 && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-gray-400 hover:text-red-500"
                        onClick={() => handleDeleteVersion(currentVerId)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>删除当前版本</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          )}
          {modelName && (
            <Badge variant="secondary" className="bg-pink-100 text-xs text-pink-700">
              {modelName}
            </Badge>
          )}
          {styleName && (
            <Badge variant="secondary" className="bg-cyan-100 text-xs text-cyan-700">
              {styleName}
            </Badge>
          )}
        </div>

        {/* 右：操作按钮 */}
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleCopy}>
            <Copy className="mr-1 h-3.5 w-3.5" />
            {copied ? '已复制' : '复制'}
          </Button>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleDownload}>
            <Download className="mr-1 h-3.5 w-3.5" />
            导出
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => setShowTranscript(v => !v)}
          >
            原文参照
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-gray-400 hover:text-red-500"
            onClick={() => onDelete(task.id)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* 正文 */}
      <div className="flex flex-1 overflow-hidden">
        <ScrollArea className="flex-1">
          <div className="markdown-body px-8 py-6 text-sm">
            <ReactMarkdown
              remarkPlugins={remarkPlugins}
              rehypePlugins={rehypePlugins}
              components={markdownComponents}
            >
              {selectedContent}
            </ReactMarkdown>
          </div>
        </ScrollArea>

        {/* 原文参照侧边栏 */}
        {showTranscript && task.transcript?.segments && (
          <div className="w-72 shrink-0 overflow-hidden border-l bg-neutral-50">
            <div className="flex items-center justify-between border-b px-3 py-2">
              <span className="text-xs font-medium text-gray-600">原文参照</span>
              <button
                onClick={() => setShowTranscript(false)}
                className="text-xs text-gray-400 hover:text-gray-700"
              >
                收起
              </button>
            </div>
            <ScrollArea className="h-[calc(100%-36px)]">
              <div className="space-y-2 p-3">
                {task.transcript.segments.map((seg, i) => (
                  <div key={i} className="text-xs">
                    <span className="font-mono text-gray-400">
                      {new Date(seg.start * 1000).toISOString().substr(14, 5)}
                    </span>
                    <span className="ml-2 text-gray-700">{seg.text}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>
    </div>
  )
}
