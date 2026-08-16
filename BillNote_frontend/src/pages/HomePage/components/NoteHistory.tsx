import { type FC, useEffect, useMemo, useState } from 'react'
import Fuse from 'fuse.js'
import { CheckSquare, Folder, FolderCog, ListChecks, Search, Square, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'

import LazyImage from '@/components/LazyImage'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import ProjectManagerDialog from '@/pages/HomePage/components/ProjectManagerDialog'
import { type HistorySort, useTaskStore } from '@/store/taskStore'

interface NoteHistoryProps {
  onSelect: (taskId: string) => void
  selectedId: string | null
}

const UNFILED = 'unfiled'
const titleCollator = new Intl.Collator('zh-CN', {
  numeric: true,
  sensitivity: 'base',
})

const formatTime = (value?: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const NoteHistory: FC<NoteHistoryProps> = ({ onSelect, selectedId }) => {
  const tasks = useTaskStore(state => state.tasks)
  const projects = useTaskStore(state => state.projects)
  const selectedProjectId = useTaskStore(state => state.selectedProjectId)
  const historySort = useTaskStore(state => state.historySort)
  const removeTask = useTaskStore(state => state.removeTask)
  const moveTaskToProject = useTaskStore(state => state.moveTaskToProject)
  const moveTasksToProject = useTaskStore(state => state.moveTasksToProject)
  const setSelectedProject = useTaskStore(state => state.setSelectedProject)
  const setHistorySort = useTaskStore(state => state.setHistorySort)
  const [rawSearch, setRawSearch] = useState('')
  const [search, setSearch] = useState('')
  const [managerOpen, setManagerOpen] = useState(false)
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const baseURL = (String(import.meta.env.VITE_API_BASE_URL || 'api')).replace(/\/$/, '')
  const projectById = useMemo(
    () => new Map(projects.map(project => [project.id, project])),
    [projects]
  )
  const fuse = useMemo(() => new Fuse(tasks, {
    keys: ['audioMeta.title'],
    threshold: 0.4,
  }), [tasks])

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(rawSearch.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [rawSearch])

  useEffect(() => {
    const existingIds = new Set(tasks.map(task => task.id))
    setSelectedIds(previous => {
      const next = new Set([...previous].filter(id => existingIds.has(id)))
      return next.size === previous.size ? previous : next
    })
  }, [tasks])

  const filteredTasks = useMemo(() => {
    const matchedIds = search
      ? new Set(fuse.search(search).map(result => result.item.id))
      : null
    const result = tasks.filter(task => {
      if (matchedIds && !matchedIds.has(task.id)) return false
      if (selectedProjectId === 'all') return true
      if (selectedProjectId === UNFILED) return !task.projectId
      return task.projectId === selectedProjectId
    })

    return [...result].sort((left, right) => {
      if (historySort === 'title') {
        const titleOrder = titleCollator.compare(
          left.audioMeta.title || '未命名笔记',
          right.audioMeta.title || '未命名笔记'
        )
        if (titleOrder !== 0) return titleOrder
      }
      if (historySort === 'earliest') {
        return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime()
      }
      return new Date(right.lastGeneratedAt || right.createdAt).getTime()
        - new Date(left.lastGeneratedAt || left.createdAt).getTime()
    })
  }, [fuse, historySort, search, selectedProjectId, tasks])

  const toggleSelected = (taskId: string) => {
    setSelectedIds(previous => {
      const next = new Set(previous)
      if (next.has(taskId)) next.delete(taskId)
      else next.add(taskId)
      return next
    })
  }

  const allVisibleSelected = filteredTasks.length > 0
    && filteredTasks.every(task => selectedIds.has(task.id))

  const toggleAllVisible = () => {
    setSelectedIds(previous => {
      const next = new Set(previous)
      if (allVisibleSelected) filteredTasks.forEach(task => next.delete(task.id))
      else filteredTasks.forEach(task => next.add(task.id))
      return next
    })
  }

  const handleBulkMove = (value: string) => {
    if (selectedIds.size === 0) return
    const projectId = value === UNFILED ? null : value
    moveTasksToProject([...selectedIds], projectId)
    const targetName = projectId ? projectById.get(projectId)?.name : '未归类'
    toast.success(`已将 ${selectedIds.size} 条笔记移动到“${targetName}”`)
    setSelectedIds(new Set())
  }

  const stopSelectionMode = () => {
    setSelectionMode(false)
    setSelectedIds(new Set())
  }

  return (
    <>
      <div className="mb-3 space-y-2">
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-neutral-400" />
          <Input
            type="text"
            placeholder="搜索笔记标题..."
            className="h-8 pl-8 text-sm"
            value={rawSearch}
            onChange={event => setRawSearch(event.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Select value={selectedProjectId} onValueChange={setSelectedProject}>
            <SelectTrigger size="sm" className="w-full min-w-0">
              <Folder className="h-4 w-4" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部项目（{tasks.length}）</SelectItem>
              <SelectItem value={UNFILED}>
                未归类（{tasks.filter(task => !task.projectId).length}）
              </SelectItem>
              {projects.map(project => (
                <SelectItem key={project.id} value={project.id}>
                  {project.name}（{tasks.filter(task => task.projectId === project.id).length}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={historySort} onValueChange={value => setHistorySort(value as HistorySort)}>
            <SelectTrigger size="sm" className="w-full min-w-0">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="latest">最后生成时间</SelectItem>
              <SelectItem value="earliest">最早生成时间</SelectItem>
              <SelectItem value="title">标题字母/数字</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => setManagerOpen(true)}
          >
            <FolderCog className="h-4 w-4" />
            管理项目
          </Button>
          <Button
            type="button"
            size="sm"
            variant={selectionMode ? 'secondary' : 'outline'}
            className="flex-1"
            onClick={() => selectionMode ? stopSelectionMode() : setSelectionMode(true)}
          >
            <ListChecks className="h-4 w-4" />
            {selectionMode ? '退出整理' : '批量整理'}
          </Button>
        </div>

        {selectionMode && (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-2">
            <div className="mb-2 flex items-center justify-between text-xs text-blue-800">
              <button type="button" className="flex items-center gap-1" onClick={toggleAllVisible}>
                {allVisibleSelected
                  ? <CheckSquare className="h-4 w-4" />
                  : <Square className="h-4 w-4" />}
                全选当前列表
              </button>
              <span>已选 {selectedIds.size} 条</span>
            </div>
            <Select disabled={selectedIds.size === 0} onValueChange={handleBulkMove}>
              <SelectTrigger size="sm" className="w-full bg-white">
                <SelectValue placeholder="移动所选笔记到..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNFILED}>未归类</SelectItem>
                {projects.map(project => (
                  <SelectItem key={project.id} value={project.id}>{project.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {filteredTasks.length === 0 ? (
        <div className="rounded-md border border-neutral-200 bg-neutral-50 py-6 text-center">
          <p className="text-sm text-neutral-500">
            {search ? '没有匹配的笔记' : '当前项目暂无笔记'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2 overflow-hidden">
          {filteredTasks.map(task => {
            const taskSelected = selectedIds.has(task.id)
            const project = task.projectId ? projectById.get(task.projectId) : null
            return (
              <div
                key={task.id}
                onClick={() => selectionMode ? toggleSelected(task.id) : onSelect(task.id)}
                className={cn(
                  'flex cursor-pointer flex-col rounded-md border border-neutral-200 p-3',
                  selectedId === task.id && !selectionMode && 'border-primary bg-primary-light',
                  taskSelected && 'border-blue-500 bg-blue-50'
                )}
              >
                <div className="flex items-center gap-3">
                  {selectionMode && (
                    <button
                      type="button"
                      onClick={event => {
                        event.stopPropagation()
                        toggleSelected(task.id)
                      }}
                      aria-label={taskSelected ? '取消选择' : '选择笔记'}
                    >
                      {taskSelected
                        ? <CheckSquare className="h-4 w-4 text-blue-600" />
                        : <Square className="h-4 w-4 text-neutral-400" />}
                    </button>
                  )}

                  {task.platform === 'local' ? (
                    <img
                      src={task.audioMeta.cover_url || '/placeholder.png'}
                      alt="封面"
                      className="h-10 w-12 rounded-md object-cover"
                    />
                  ) : (
                    <LazyImage
                      src={task.audioMeta.cover_url
                        ? `${baseURL}/image_proxy?url=${encodeURIComponent(task.audioMeta.cover_url)}`
                        : '/placeholder.png'}
                      alt="封面"
                    />
                  )}

                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="line-clamp-2 min-w-0 flex-1 overflow-hidden text-sm text-ellipsis">
                          {task.audioMeta.title || '未命名笔记'}
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>{task.audioMeta.title || '未命名笔记'}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>

                <div className="mt-2 flex items-center justify-between gap-2 text-[10px]">
                  <div className="flex items-center gap-2">
                    {task.status === 'SUCCESS' ? (
                      <span className="bg-primary w-10 rounded p-0.5 text-center text-white">已完成</span>
                    ) : task.status === 'FAILED' ? (
                      <span className="w-10 rounded bg-red-500 p-0.5 text-center text-white">失败</span>
                    ) : (
                      <span className="w-10 rounded bg-green-500 p-0.5 text-center text-white">进行中</span>
                    )}
                    <span className="text-neutral-400">
                      {formatTime(task.lastGeneratedAt || task.createdAt)}
                    </span>
                  </div>
                </div>

                {!selectionMode && (
                  <div className="mt-2 flex items-center gap-2 border-t border-neutral-100 pt-2">
                    <div className="min-w-0 flex-1" onClick={event => event.stopPropagation()}>
                      <Select
                        value={task.projectId || UNFILED}
                        onValueChange={value => {
                          moveTaskToProject(task.id, value === UNFILED ? null : value)
                          const targetName = value === UNFILED
                            ? '未归类'
                            : projectById.get(value)?.name
                          toast.success(`已移动到“${targetName}”`)
                        }}
                      >
                        <SelectTrigger size="sm" className="h-7 w-full min-w-0 text-xs">
                          <Folder className="h-3.5 w-3.5" />
                          <SelectValue>{project?.name || '未归类'}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={UNFILED}>未归类</SelectItem>
                          {projects.map(item => (
                            <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={event => {
                        event.stopPropagation()
                        removeTask(task.id)
                      }}
                      aria-label="删除笔记"
                    >
                      <Trash2 className="text-muted-foreground h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <ProjectManagerDialog open={managerOpen} onOpenChange={setManagerOpen} />
    </>
  )
}

export default NoteHistory
