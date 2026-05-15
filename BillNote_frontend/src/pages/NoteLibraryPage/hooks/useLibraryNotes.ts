import { useMemo } from 'react'
import { useTaskStore, type Task, type TaskStatus } from '@/store/taskStore'
import { noteStyles, videoPlatforms } from '@/constant/note'

export type StatusFilter = 'all' | 'success' | 'failed' | 'running'
export type SortOrder = 'desc' | 'asc'

export interface LibraryFilters {
  status: StatusFilter
  model: string
  style: string
  platform: string
  sort: SortOrder
}

export interface LibraryNote {
  id: string
  title: string
  status: TaskStatus
  coverUrl: string
  platform: string
  videoId: string
  createdAt: string
  duration: number
  modelName: string
  style: string
  versionCount: number
  hasMarkdown: boolean
  videoUnderstanding?: boolean
  screenshot?: boolean
  link?: boolean
}

const RUNNING_STATUSES: TaskStatus[] = [
  'PENDING', 'RUNNING', 'PARSING', 'DOWNLOADING',
  'TRANSCRIBING', 'ANALYZING_VIDEO', 'SUMMARIZING', 'SAVING',
]

function toLibraryNote(task: Task): LibraryNote {
  const markdowns = Array.isArray(task.markdown) ? task.markdown : []
  const hasMarkdown = markdowns.length > 0 || (typeof task.markdown === 'string' && task.markdown.length > 0)
  const modelName = markdowns[0]?.model_name || task.formData?.model_name || ''
  const style = markdowns[0]?.style || task.formData?.style || ''

  return {
    id: task.id,
    title: task.audioMeta?.title || task.id,
    status: task.status,
    coverUrl: task.audioMeta?.cover_url || '',
    platform: task.audioMeta?.platform || task.formData?.platform || '',
    videoId: task.audioMeta?.video_id || '',
    createdAt: task.createdAt || '',
    duration: task.audioMeta?.duration || 0,
    modelName,
    style,
    versionCount: markdowns.length,
    hasMarkdown,
    videoUnderstanding: task.formData?.video_understanding,
    screenshot: task.formData?.screenshot,
    link: task.formData?.link,
  }
}

export function useLibraryNotes(filters: LibraryFilters, searchResults: string[] | null) {
  const tasks = useTaskStore(state => state.tasks)

  return useMemo(() => {
    let notes = tasks.map(toLibraryNote)

    // status filter
    if (filters.status === 'success') {
      notes = notes.filter(n => n.status === 'SUCCESS')
    } else if (filters.status === 'failed') {
      notes = notes.filter(n => n.status === 'FAILED')
    } else if (filters.status === 'running') {
      notes = notes.filter(n => RUNNING_STATUSES.includes(n.status))
    }

    // model filter
    if (filters.model) {
      notes = notes.filter(n => n.modelName === filters.model)
    }

    // style filter
    if (filters.style) {
      notes = notes.filter(n => n.style === filters.style)
    }

    // platform filter
    if (filters.platform) {
      notes = notes.filter(n => n.platform === filters.platform)
    }

    // search filter
    if (searchResults) {
      const idSet = new Set(searchResults)
      notes = notes.filter(n => idSet.has(n.id))
    }

    // sort
    notes = [...notes].sort((a, b) => {
      const ta = new Date(a.createdAt).getTime() || 0
      const tb = new Date(b.createdAt).getTime() || 0
      return filters.sort === 'desc' ? tb - ta : ta - tb
    })

    return notes
  }, [tasks, filters, searchResults])
}

export function useLibraryOptions() {
  const tasks = useTaskStore(state => state.tasks)

  return useMemo(() => {
    const modelSet = new Set<string>()
    const platformSet = new Set<string>()

    for (const task of tasks) {
      const markdowns = Array.isArray(task.markdown) ? task.markdown : []
      const model = markdowns[0]?.model_name || task.formData?.model_name || ''
      if (model) modelSet.add(model)
      const platform = task.audioMeta?.platform || task.formData?.platform || ''
      if (platform) platformSet.add(platform)
    }

    const platformLabels = Object.fromEntries(videoPlatforms.map(p => [p.value, p.label]))
    const styleLabels = Object.fromEntries(noteStyles.map(s => [s.value, s.label]))

    return {
      models: Array.from(modelSet).sort(),
      platforms: Array.from(platformSet).map(v => ({ value: v, label: platformLabels[v] || v })),
      styles: noteStyles.map(s => ({ value: s.value, label: s.label })),
      styleLabels,
      platformLabels,
    }
  }, [tasks])
}
