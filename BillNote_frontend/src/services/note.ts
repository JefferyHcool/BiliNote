import request from '@/utils/request'
import toast from 'react-hot-toast'
import { useTaskStore } from '@/store/taskStore'

const DOWNLOAD_QUALITIES = ['fast', 'medium', 'slow'] as const
type DownloadQualityValue = (typeof DOWNLOAD_QUALITIES)[number]

export const normalizeDownloadQuality = (quality: unknown): DownloadQualityValue => {
  const raw = typeof quality === 'string' ? quality : ''
  const value = raw.includes('.') ? raw.split('.').pop() || '' : raw
  return DOWNLOAD_QUALITIES.includes(value as DownloadQualityValue)
    ? (value as DownloadQualityValue)
    : 'medium'
}

const normalizeBoundedInteger = (value: unknown, fallback: number, min: number, max: number) => {
  const numberValue = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(numberValue)) return fallback
  return Math.max(min, Math.min(max, Math.trunc(numberValue)))
}

export const normalizeVideoInterval = (interval: unknown) => {
  const n = typeof interval === 'number' ? interval : Number(interval)
  if (!Number.isFinite(n) || n <= 0) return 6
  return Math.max(1, Math.min(30, Math.trunc(n)))
}

export const normalizeGridSize = (gridSize: unknown): [number, number] => {
  if (!Array.isArray(gridSize)) return [2, 2]
  return [
    normalizeBoundedInteger(gridSize[0], 2, 1, 10),
    normalizeBoundedInteger(gridSize[1], 2, 1, 10),
  ]
}

export const syncNotes = async () => {
  try {
    // 拦截器已解包，直接拿到数组
    const backendNotes = (await request.get('/notes')) as any[]
    if (!Array.isArray(backendNotes)) return

    const mapStatus = (s: string) => {
      if (s === 'SUCCESS') return 'SUCCESS'
      if (s === 'FAILED') return 'FAILED'
      return 'PENDING'
    }

    const mergePresent = (base: Record<string, any> = {}, incoming: Record<string, any> = {}) => {
      const next = { ...base }
      Object.entries(incoming).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          next[key] = value
        }
      })
      return next
    }

    const toTask = (item: any) => {
      const generationParams = item.generation_params ?? {}
      return {
        id: item.task_id,
        status: mapStatus(item.status) as any,
        markdown: '',
        transcript: { full_text: '', language: '', raw: null, segments: [] },
        createdAt: typeof item.created_at === 'number'
            ? new Date(item.created_at * 1000).toISOString()
            : item.created_at || new Date().toISOString(),
        audioMeta: {
          title: item.title || item.task_id,
          duration: item.duration || 0,
          cover_url: item.cover_url || '',
          video_id: item.video_id || '',
          file_path: '',
          platform: item.platform || '',
          raw_info: {},
        },
        formData: {
          video_url: generationParams.video_url || '',
          link: generationParams.link ?? undefined,
          screenshot: generationParams.screenshot ?? undefined,
          platform: generationParams.platform || item.platform || '',
          quality: normalizeDownloadQuality(generationParams.quality),
          model_name: generationParams.model_name || '',
          provider_id: generationParams.provider_id || '',
          style: generationParams.style || '',
          extras: generationParams.extras || '',
          video_understanding: generationParams.video_understanding ?? undefined,
          video_interval: normalizeVideoInterval(generationParams.video_interval),
          grid_size: normalizeGridSize(generationParams.grid_size),
        },
      }
    }

    const syncedTasks = backendNotes.map(toTask)
    const syncedById = new Map(syncedTasks.map(task => [task.id, task]))

    useTaskStore.setState(state => {
      const tasksToAdd = new Map(syncedById)
      const mergedTasks = state.tasks
        .filter(task => {
          if (syncedById.has(task.id)) return true
          // 后端已不知道该任务（被另一个浏览器删除，或从未同步上来）
          const isTerminal = task.status === 'SUCCESS' || task.status === 'FAILED'
          // 终态任务：后端没有 → 已被删，直接移除
          if (isTerminal) return false
          // 非终态任务：给 60s 宽限期，避免刚提交的任务因 /notes 还没收录而被误删
          const age = Date.now() - new Date(task.createdAt || 0).getTime()
          return age < 60_000
        })
        .map(task => {
          const synced = syncedById.get(task.id)
          if (!synced) return task
          tasksToAdd.delete(task.id)
          // 任务仍在运行时，不允许后端旧 JSON 的 formData 覆盖本地刚提交的参数
          // （防止用 mimo 重提交后切换 Qwen，mimo 先完成时把 formData 写回 Qwen）
          const localIsRunning = task.status !== 'SUCCESS' && task.status !== 'FAILED'
          return {
            ...task,
            status: synced.status,
            createdAt: task.createdAt || synced.createdAt,
            audioMeta: mergePresent(task.audioMeta, synced.audioMeta),
            formData: localIsRunning ? task.formData : mergePresent(task.formData, synced.formData),
          }
        })

      const allTasks = [...mergedTasks, ...Array.from(tasksToAdd.values())]
      return {
        tasks: allTasks,
        currentTaskId: allTasks.some(t => t.id === state.currentTaskId)
          ? state.currentTaskId
          : null,
        }
    })
  } catch (e) {
    console.error('同步笔记失败', e)
  }
}

export const generateNote = async (data: {
  video_url: string
  platform: string
  quality: string
  model_name: string
  provider_id: string
  task_id?: string
  format: Array<string>
  style: string
  extras?: string
  video_understand?: boolean
  video_interval?: number
  grid_size: Array<number>
}) => {
  try {
    const payload = {
      ...data,
      quality: normalizeDownloadQuality(data.quality),
      video_interval: normalizeVideoInterval(data.video_interval),
      grid_size: normalizeGridSize(data.grid_size),
    }
    console.log('generateNote', payload)
    const response = await request.post('/generate_note', payload)

    if (!response) {
      return null
    }
    toast.success('笔记生成任务已提交！')

    console.log('res', response)
    // 成功提示

    return response
  } catch (e: any) {
    console.error('❌ 请求出错', e)

    // 错误提示
    // toast.error('笔记生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
  }
}

export const delete_task = async ({ task_id, video_id, platform }: { task_id: string; video_id?: string; platform?: string }) => {
  try {
    const data = { task_id, video_id, platform }
    const res = await request.post('/delete_task', data)


      toast.success('任务已成功删除')
      return res
  } catch (e) {
    toast.error('请求异常，删除任务失败')
    console.error('❌ 删除任务失败:', e)
    throw e
  }
}

export const delete_note_version = async (task_id: string, ver_id: string) => {
  try {
    const res = await request.post('/delete_note_version', { task_id, ver_id })
    return res
  } catch (e) {
    toast.error('删除版本失败')
    throw e
  }
}

export const cancel_task = async (task_id: string) => {
  try {
    const res = await request.post('/cancel_task', { task_id })
    toast.success('任务已取消')
    return res
  } catch (e) {
    toast.error('取消失败')
    throw e
  }
}

export const get_task_status = async (
  task_id: string,
  options?: { includeTranscript?: boolean }
) => {
  try {
    // 成功提示

    const config =
      options?.includeTranscript === false
        ? { params: { include_transcript: false } }
        : undefined

    return await request.get('/task_status/' + task_id, config)
  } catch (e) {
    console.error('❌ 请求出错', e)

    // 错误提示
    toast.error('笔记生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
  }
}
