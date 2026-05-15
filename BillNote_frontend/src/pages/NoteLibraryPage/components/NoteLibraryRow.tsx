import { Trash2, Layers } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import LazyImage from '@/components/LazyImage'
import type { LibraryNote } from '../hooks/useLibraryNotes'

interface NoteLibraryRowProps {
  note: LibraryNote
  selected: boolean
  onSelect: () => void
  onDelete: () => void
  styleLabel: string
  platformLabel: string
  baseURL: string
}

const STATUS_BADGE: Record<string, { label: string; class: string }> = {
  SUCCESS:  { label: '已完成', class: 'bg-green-100 text-green-700' },
  FAILED:   { label: '失败',   class: 'bg-red-100 text-red-600' },
  PENDING:  { label: '排队中', class: 'bg-gray-100 text-gray-500' },
  RUNNING:  { label: '运行中', class: 'bg-blue-100 text-blue-600' },
  PARSING:         { label: '解析中',   class: 'bg-blue-100 text-blue-600' },
  DOWNLOADING:     { label: '下载中',   class: 'bg-blue-100 text-blue-600' },
  TRANSCRIBING:    { label: '转写中',   class: 'bg-indigo-100 text-indigo-600' },
  ANALYZING_VIDEO: { label: '分析中',   class: 'bg-purple-100 text-purple-600' },
  SUMMARIZING:     { label: '总结中',   class: 'bg-amber-100 text-amber-600' },
  SAVING:          { label: '保存中',   class: 'bg-green-100 text-green-600' },
}

function formatDuration(seconds: number) {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m${s > 0 ? `${s}s` : ''}` : `${s}s`
}

function formatDate(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).replace(/\//g, '-')
}

export function NoteLibraryRow({
  note,
  selected,
  onSelect,
  onDelete,
  styleLabel,
  platformLabel,
  baseURL,
}: NoteLibraryRowProps) {
  const badge = STATUS_BADGE[note.status] ?? { label: note.status, class: 'bg-gray-100 text-gray-500' }
  const coverSrc = note.coverUrl
    ? note.coverUrl.startsWith('http')
      ? `${baseURL}/image_proxy?url=${encodeURIComponent(note.coverUrl)}`
      : `${baseURL}/${note.coverUrl.replace(/^\//, '')}`
    : ''

  return (
    <div
      onClick={onSelect}
      className={cn(
        'group flex cursor-pointer items-center gap-3 border-b border-neutral-100 px-4 py-2.5 text-sm transition-colors hover:bg-neutral-50',
        selected && 'bg-primary/5 hover:bg-primary/5'
      )}
    >
      {/* 封面 */}
      <div className="h-10 w-14 shrink-0 overflow-hidden rounded">
        {coverSrc ? (
          <LazyImage src={coverSrc} alt={note.title} className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full rounded bg-neutral-100" />
        )}
      </div>

      {/* 标题 + 元信息 */}
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-gray-800 leading-snug">{note.title}</p>
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-gray-400">
          {platformLabel && <span>{platformLabel}</span>}
          {note.modelName && <span className="text-gray-400">·</span>}
          {note.modelName && <span className="max-w-[90px] truncate">{note.modelName}</span>}
          {styleLabel && <span className="text-gray-400">·</span>}
          {styleLabel && <span>{styleLabel}</span>}
          {note.duration > 0 && <span className="text-gray-400">·</span>}
          {note.duration > 0 && <span>{formatDuration(note.duration)}</span>}
        </div>
      </div>

      {/* 右侧徽章 + 操作 */}
      <div className="flex shrink-0 items-center gap-2">
        {note.versionCount > 1 && (
          <span className="flex items-center gap-0.5 text-xs text-gray-400">
            <Layers className="h-3 w-3" />{note.versionCount}
          </span>
        )}
        <Badge className={cn('h-5 px-1.5 text-xs font-normal', badge.class)}>
          {badge.label}
        </Badge>
        <span className="hidden text-xs text-gray-400 group-hover:hidden sm:block">
          {formatDate(note.createdAt)}
        </span>
        <button
          onClick={e => { e.stopPropagation(); onDelete() }}
          className="ml-1 hidden rounded p-1 text-gray-300 hover:text-red-500 group-hover:block"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
