import request from '@/utils/request'
import toast from 'react-hot-toast'
import { useTaskStore } from '@/store/taskStore'

export const syncNotes = async () => {
  try {
    // 拦截器已解包，直接拿到数组
    const backendNotes = (await request.get('/notes')) as any[]
    if (!Array.isArray(backendNotes)) return

    const localTasks = useTaskStore.getState().tasks
    const localIds = new Set(localTasks.map(t => t.id))

    const mapStatus = (s: string) => {
      if (s === 'SUCCESS') return 'SUCCESS'
      if (s === 'FAILED') return 'FAILED'
      return 'PENDING'
    }

    // 只补本地没有的条目，不覆盖已有的完整任务
    const newTasks = backendNotes
      .filter(item => !localIds.has(item.task_id))
      .map(item => ({
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
          video_url: item.generation_params?.video_url || '',
          link: item.generation_params?.link ?? undefined,
          screenshot: item.generation_params?.screenshot ?? undefined,
          platform: item.generation_params?.platform || item.platform || '',
          quality: item.generation_params?.quality || '',
          model_name: item.generation_params?.model_name || '',
          provider_id: item.generation_params?.provider_id || '',
          style: item.generation_params?.style || '',
          extras: item.generation_params?.extras || '',
          video_understanding: item.generation_params?.video_understanding ?? undefined,
          video_interval: item.generation_params?.video_interval ?? undefined,
          grid_size: item.generation_params?.grid_size ?? undefined,
        },
      }))

    if (newTasks.length > 0) {
      useTaskStore.setState(state => ({
        tasks: [...state.tasks, ...newTasks],
      }))
    }
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
    console.log('generateNote', data)
    const response = await request.post('/generate_note', data)

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
