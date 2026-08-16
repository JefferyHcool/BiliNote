import request from '@/utils/request'
import toast from 'react-hot-toast'

export interface GenerateNotePayload {
  video_url: string
  platform: string
  quality: string
  model_name: string
  provider_id: string
  task_id?: string
  format: Array<string>
  style: string
  extras?: string
  screenshot?: boolean
  link?: boolean
  video_understanding?: boolean
  video_interval?: number
  grid_size: Array<number>
  prefetched_transcript?: Record<string, unknown>
}

export interface BatchTaskItem {
  task_id: string
  p: number
  video_url: string
  title: string
}

export interface GenerateNoteBatchResult {
  batch_id: string
  total: number
  max_parallel: number
  series_title: string
  tasks: BatchTaskItem[]
}

export const generateNote = async (data: GenerateNotePayload) => {
  try {
    console.log('generateNote', data)
    const response = await request.post('/generate_note', data)

    if (!response) {
      if (response.data.msg) {
        toast.error(response.data.msg)
      }
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

export const generateNoteBatch = async (
  data: GenerateNotePayload & { p_start: number; p_end: number }
): Promise<GenerateNoteBatchResult> => {
  try {
    // 后端会先请求一次 B 站分集清单并校验范围，代理较慢时可能超过全局 10 秒。
    return await request.post('/generate_note_batch', data, { timeout: 30000 })
  } catch (e: any) {
    console.error('❌ 批量任务提交失败', e)
    throw e
  }
}

export const delete_task = async ({ video_id, platform }) => {
  try {
    const data = {
      video_id,
      platform,
    }
    const res = await request.post('/delete_task', data)


      toast.success('任务已成功删除')
      return res
  } catch (e) {
    toast.error('请求异常，删除任务失败')
    console.error('❌ 删除任务失败:', e)
    throw e
  }
}

export const get_task_status = async (task_id: string) => {
  try {
    // 成功提示

    return await request.get('/task_status/' + task_id)
  } catch (e) {
    console.error('❌ 请求出错', e)

    // 错误提示
    toast.error('笔记生成失败，请稍后重试')

    throw e // 抛出错误以便调用方处理
  }
}
