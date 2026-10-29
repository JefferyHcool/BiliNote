import { useEffect, useMemo, useState, type FC } from 'react'
import Fuse from 'fuse.js'
import JSZip from 'jszip'
import { Download, FolderOpen, Loader2, Trash } from 'lucide-react'
import toast from 'react-hot-toast'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Checkbox } from '@/components/ui/checkbox.tsx'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import LazyImage from '@/components/LazyImage.tsx'
import { cn } from '@/lib/utils.ts'
import { useTaskStore, type Task } from '@/store/taskStore'

interface NoteHistoryProps {
  onSelect: (taskId: string) => void
  selectedId: string | null
}

interface FavoriteCategory {
  id: string
  title: string
  count: number
}

const getMarkdownContent = (task: Task) => {
  if (typeof task.markdown === 'string') return task.markdown
  if (task.markdown.length === 0) return ''

  const latest = task.markdown.reduce((current, candidate) => {
    return Date.parse(candidate.created_at || '') > Date.parse(current.created_at || '')
      ? candidate
      : current
  })
  return latest.content || ''
}

const isExportableTask = (task: Task) =>
  task.status === 'SUCCESS' && Boolean(getMarkdownContent(task).trim())

const safePathSegment = (value: string) => Array.from(value.trim(), character => {
  const code = character.charCodeAt(0)
  return /[<>:"/\\|?*]/.test(character) || code < 32 || code === 127 ? '_' : character
}).join('').replace(/[. ]+$/g, '') || '未命名笔记'

const NoteHistory: FC<NoteHistoryProps> = ({ onSelect, selectedId }) => {
  const tasks = useTaskStore(state => state.tasks)
  const removeTask = useTaskStore(state => state.removeTask)
  const baseURL = (String(import.meta.env.VITE_API_BASE_URL || 'api')).replace(/\/$/, '')
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [selectedExportIds, setSelectedExportIds] = useState<string[]>([])
  const [isExporting, setIsExporting] = useState(false)

  const favoriteCategories = useMemo(() => {
    const categories = new Map<string, FavoriteCategory>()
    tasks.forEach(task => {
      const folder = task.favoriteFolder
      if (!folder) return
      const existing = categories.get(folder.id)
      if (existing) existing.count += 1
      else categories.set(folder.id, { id: folder.id, title: folder.title, count: 1 })
    })
    return [...categories.values()]
  }, [tasks])

  useEffect(() => {
    if (sourceFilter.startsWith('favorite:') &&
      !favoriteCategories.some(category => `favorite:${category.id}` === sourceFilter)) {
      setSourceFilter('all')
    }
  }, [favoriteCategories, sourceFilter])

  const fuse = useMemo(() => new Fuse(tasks, {
    keys: ['audioMeta.title', 'favoriteFolder.title'],
    threshold: 0.4,
  }), [tasks])

  const filteredTasks = useMemo(() => {
    const sourceTasks = tasks.filter(task => {
      if (sourceFilter === 'ordinary') return !task.favoriteFolder
      if (sourceFilter.startsWith('favorite:')) {
        return task.favoriteFolder?.id === sourceFilter.slice('favorite:'.length)
      }
      return true
    })
    if (!search.trim()) return sourceTasks

    const sourceTaskIds = new Set(sourceTasks.map(task => task.id))
    return fuse.search(search.trim())
      .map(result => result.item)
      .filter(task => sourceTaskIds.has(task.id))
  }, [tasks, sourceFilter, search, fuse])

  const exportableTasks = filteredTasks.filter(isExportableTask)
  const selectedExportTasks = tasks.filter(task =>
    selectedExportIds.includes(task.id) && isExportableTask(task)
  )
  const visibleExportIds = exportableTasks.map(task => task.id)
  const selectedVisibleCount = visibleExportIds.filter(id => selectedExportIds.includes(id)).length
  const allVisibleSelected = visibleExportIds.length > 0 && selectedVisibleCount === visibleExportIds.length
  const someVisibleSelected = selectedVisibleCount > 0 && !allVisibleSelected
  const ordinaryCount = tasks.filter(task => !task.favoriteFolder).length

  const toggleVisibleSelection = () => {
    setSelectedExportIds(current => {
      const visibleSet = new Set(visibleExportIds)
      const alreadyAllSelected = visibleExportIds.length > 0 && visibleExportIds.every(id => current.includes(id))
      if (alreadyAllSelected) return current.filter(id => !visibleSet.has(id))
      return [...new Set([...current, ...visibleExportIds])]
    })
  }

  const exportSelectedNotes = async () => {
    if (selectedExportTasks.length === 0) return
    setIsExporting(true)
    try {
      const archive = new JSZip()
      const usedPaths = new Set<string>()

      selectedExportTasks.forEach(task => {
        const folderName = safePathSegment(task.favoriteFolder?.title || '普通任务')
        const baseName = safePathSegment(task.favoriteVideo?.title || task.audioMeta.title || `笔记-${task.id.slice(0, 8)}`)
        let fileName = baseName
        let suffix = 2
        let path = `${folderName}/${fileName}.md`
        while (usedPaths.has(path)) {
          fileName = `${baseName} (${suffix})`
          suffix += 1
          path = `${folderName}/${fileName}.md`
        }
        usedPaths.add(path)
        archive.file(path, getMarkdownContent(task))
      })

      const blob = await archive.generateAsync({ type: 'blob' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `BiliNote-批量笔记-${new Date().toISOString().slice(0, 10)}.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast.success(`已打包 ${selectedExportTasks.length} 篇 Markdown`)
    } catch (error) {
      console.error('批量导出 Markdown 失败:', error)
      toast.error('批量导出失败')
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <>
      <div className="mb-2 flex flex-col gap-2">
        <input
          type="text"
          placeholder="搜索笔记标题或收藏夹..."
          className="w-full rounded border border-neutral-300 px-3 py-1 text-sm outline-none focus:border-primary"
          value={search}
          onChange={event => setSearch(event.target.value)}
        />
        <Select value={sourceFilter} onValueChange={setSourceFilter}>
          <SelectTrigger className="h-8 w-full text-sm">
            <SelectValue placeholder="按来源筛选" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部来源 ({tasks.length})</SelectItem>
            <SelectItem value="ordinary">普通任务 ({ordinaryCount})</SelectItem>
            {favoriteCategories.map(category => (
              <SelectItem key={category.id} value={`favorite:${category.id}`}>
                {category.title} ({category.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mb-2 flex items-center justify-between gap-2">
        <label className="flex min-w-0 cursor-pointer items-center gap-2 text-xs text-muted-foreground">
          <Checkbox
            checked={allVisibleSelected ? true : someVisibleSelected ? 'indeterminate' : false}
            disabled={exportableTasks.length === 0 || isExporting}
            onCheckedChange={toggleVisibleSelection}
            aria-label="全选当前可导出的笔记"
          />
          <span className="truncate">全选当前可导出 ({exportableTasks.length})</span>
        </label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0"
          onClick={exportSelectedNotes}
          disabled={selectedExportTasks.length === 0 || isExporting}
        >
          {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          导出已选 ({selectedExportTasks.length})
        </Button>
      </div>

      {filteredTasks.length === 0 ? (
        <div className="rounded-md border border-neutral-200 bg-neutral-50 py-6 text-center">
          <p className="text-sm text-neutral-500">
            {tasks.length === 0 ? '暂无记录' : '当前筛选下暂无记录'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2 overflow-hidden">
          {filteredTasks.map(task => {
            const title = task.audioMeta.title || '未命名笔记'
            const canExport = isExportableTask(task)
            return (
              <div
                key={task.id}
                onClick={() => onSelect(task.id)}
                className={cn(
                  'flex w-full min-w-0 cursor-pointer flex-col rounded-md border border-neutral-200 p-3',
                  selectedId === task.id && 'border-primary bg-primary-light',
                )}
              >
                <div className="flex w-full min-w-0 items-center gap-3">
                  <Checkbox
                    checked={selectedExportIds.includes(task.id)}
                    disabled={!canExport || isExporting}
                    aria-label={`选择导出 ${title}`}
                    onClick={event => event.stopPropagation()}
                    onCheckedChange={checked => {
                      setSelectedExportIds(current => checked === true
                        ? [...new Set([...current, task.id])]
                        : current.filter(id => id !== task.id))
                    }}
                  />
                  {task.platform === 'local' ? (
                    <img
                      src={task.audioMeta.cover_url || '/placeholder.png'}
                      alt="封面"
                      className="h-10 w-12 shrink-0 rounded-md object-cover"
                    />
                  ) : (
                    <LazyImage
                      src={task.audioMeta.cover_url
                        ? `${baseURL}/image_proxy?url=${encodeURIComponent(task.audioMeta.cover_url)}`
                        : '/placeholder.png'}
                      alt="封面"
                      className="h-10 w-14 shrink-0"
                    />
                  )}

                  <div className="min-w-0 flex-1">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="min-w-0 whitespace-normal break-words text-sm leading-snug [overflow-wrap:anywhere]">
                            {title}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{title}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    {task.favoriteFolder && (
                      <Badge
                        variant="outline"
                        title={task.favoriteFolder.url}
                        className="mt-1 max-w-full gap-1 px-1.5 py-0 text-[10px]"
                      >
                        <FolderOpen className="h-3 w-3 shrink-0" />
                        <span className="truncate">{task.favoriteFolder.title}</span>
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="mt-2 flex items-center justify-between text-[10px]">
                  <div className="shrink-0">
                    {task.status === 'SUCCESS' && (
                      <div className="w-10 rounded bg-primary p-0.5 text-center text-white">已完成</div>
                    )}
                    {task.status !== 'SUCCESS' && task.status !== 'FAILED' && (
                      <div className="w-10 rounded bg-green-500 p-0.5 text-center text-white">等待中</div>
                    )}
                    {task.status === 'FAILED' && (
                      <div className="w-10 rounded bg-red-500 p-0.5 text-center text-white">失败</div>
                    )}
                  </div>

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          size="small"
                          variant="ghost"
                          onClick={event => {
                            event.stopPropagation()
                            removeTask(task.id)
                            setSelectedExportIds(current => current.filter(id => id !== task.id))
                          }}
                          className="shrink-0"
                        >
                          <Trash className="h-4 w-4 text-muted-foreground" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>删除</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}

export default NoteHistory
