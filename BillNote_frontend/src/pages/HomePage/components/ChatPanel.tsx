import { useState, useEffect, useCallback, useMemo } from 'react'
import { Bubble, Sender } from '@ant-design/x'
import type { BubbleProps } from '@ant-design/x'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Loader2, Trash2, ChevronDown, ChevronUp, BookOpen, UserRound, Bot } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { useChatStore } from '@/store/chatStore'
import { useTaskStore } from '@/store/taskStore'
import { askQuestion, getChatStatus, indexTask, type ChatSource } from '@/services/chat'

interface ChatPanelProps {
  taskId: string
}

function SourceBadges({ sources }: { sources: ChatSource[] }) {
  const [expanded, setExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-1.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-neutral-400 hover:text-neutral-600"
      >
        <BookOpen className="h-3 w-3" />
        <span>引用来源 ({sources.length})</span>
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {expanded && (
        <div className="mt-1 flex flex-wrap gap-1">
          {sources.map((s, i) => (
            <Badge key={i} variant="outline" className="text-xs font-normal">
              {s.source_type === 'markdown'
                ? s.section_title || '笔记'
                : `${(s.start_time ?? 0).toFixed(0)}s ~ ${(s.end_time ?? 0).toFixed(0)}s`}
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatPanel({ taskId }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [indexing, setIndexing] = useState(false)
  const [indexed, setIndexed] = useState<boolean | null>(null)

  const messages = useChatStore(state => state.chatHistory[taskId] || [])
  const addMessage = useChatStore(state => state.addMessage)
  const clearChat = useChatStore(state => state.clearChat)

  const currentTask = useTaskStore(state => state.getCurrentTask())

  // 检查索引状态
  useEffect(() => {
    if (!taskId) return
    let cancelled = false

    const check = async () => {
      try {
        const res = await getChatStatus(taskId)
        if (cancelled) return
        if (res.indexed) {
          setIndexed(true)
        } else {
          setIndexing(true)
          await indexTask(taskId)
          if (!cancelled) {
            setIndexed(true)
            setIndexing(false)
          }
        }
      } catch {
        if (!cancelled) {
          setIndexed(false)
          setIndexing(false)
        }
      }
    }

    check()
    return () => {
      cancelled = true
    }
  }, [taskId])

  const handleSend = useCallback(
    async (value: string) => {
      const question = value.trim()
      if (!question || loading) return

      const providerId = currentTask?.formData?.provider_id
      const modelName = currentTask?.formData?.model_name
      if (!providerId || !modelName) {
        toast.error('无法获取模型配置，请确认任务已完成')
        return
      }

      addMessage(taskId, { role: 'user', content: question })
      setInput('')
      setLoading(true)

      try {
        const history = messages.map(m => ({ role: m.role, content: m.content }))
        const res = await askQuestion({
          task_id: taskId,
          question,
          history,
          provider_id: providerId,
          model_name: modelName,
        })
        addMessage(taskId, {
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
        })
      } catch {
        toast.error('问答请求失败')
      } finally {
        setLoading(false)
      }
    },
    [loading, taskId, currentTask, messages, addMessage],
  )

  // 转换为 Bubble.List 的数据格式
  const bubbleItems = useMemo(() => {
    const items = messages.map((msg, i) => ({
      key: `msg-${i}`,
      role: msg.role === 'user' ? ('user' as const) : ('ai' as const),
      content: msg.content,
      footer:
        msg.role === 'assistant' && msg.sources ? (
          <SourceBadges sources={msg.sources} />
        ) : undefined,
    }))

    if (loading) {
      items.push({
        key: 'loading',
        role: 'ai' as const,
        content: '思考中...',
        loading: true,
      } as any)
    }

    return items
  }, [messages, loading])

  // Bubble 角色配置
  const roles: BubbleProps['roles'] = useMemo(
    () => ({
      user: {
        placement: 'end',
        avatar: {
          icon: <UserRound className="h-4 w-4" />,
          style: { background: '#3b82f6' },
        },
      },
      ai: {
        placement: 'start',
        avatar: {
          icon: <Bot className="h-4 w-4" />,
          style: { background: '#6b7280' },
        },
        typing: { step: 5, interval: 50 },
      },
    }),
    [],
  )

  if (indexing) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-neutral-400">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">正在索引笔记内容...</span>
      </div>
    )
  }

  if (indexed === false) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-neutral-400">
        <span className="text-sm">索引失败，请重试</span>
        <Button
          size="sm"
          variant="outline"
          onClick={async () => {
            setIndexing(true)
            try {
              await indexTask(taskId)
              setIndexed(true)
            } catch {
              toast.error('索引失败')
            } finally {
              setIndexing(false)
            }
          }}
        >
          重新索引
        </Button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col border-l">
      {/* 头部 */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-medium">AI 问答</span>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-neutral-400 hover:text-red-500"
            onClick={() => clearChat(taskId)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-hidden">
        {messages.length === 0 && !loading ? (
          <div className="flex h-full items-center justify-center text-center text-sm text-neutral-400">
            <div>
              <p>针对笔记内容提问</p>
              <p className="mt-1 text-xs">例如：这个视频的核心观点是什么？</p>
            </div>
          </div>
        ) : (
          <Bubble.List
            items={bubbleItems}
            roles={roles}
            style={{ height: '100%' }}
          />
        )}
      </div>

      {/* 输入区域 */}
      <div className="border-t px-3 py-2">
        <Sender
          value={input}
          onChange={setInput}
          onSubmit={handleSend}
          loading={loading}
          placeholder="输入你的问题..."
        />
      </div>
    </div>
  )
}
