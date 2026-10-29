import request from '@/utils/request'

export interface FavoriteVideo {
  bvid: string
  video_key?: string
  title: string
  cover: string
  duration: number
  uploader: string
  video_url: string
  page_number?: number
  page_count?: number
  status?: 'queued' | 'running' | 'success' | 'failed'
  task_id?: string
  resume_task_id?: string
  error?: string
}

export interface FavoritePage {
  favorite_id: string
  title: string
  media_count: number
  page: number
  page_size: number
  videos: FavoriteVideo[]
  has_more: boolean
}

export interface FavoriteBatchSnapshot {
  batch_id: string
  state: 'running' | 'paused' | 'done' | 'failed'
  favorite_folder: {
    id: string
    title: string
    url: string
  }
  videos: FavoriteVideo[]
  config: FavoriteBatchConfig
  next_index: number
  current_index: number | null
  pause_requested: boolean
}

export interface FavoriteBatchConfig {
  quality: string
  model_name: string
  provider_id: string
  screenshot?: boolean
  link?: boolean
  format: string[]
  style: string
  extras?: string
  video_understanding?: boolean
  video_interval?: number
  grid_size?: number[]
}

export const getBilibiliFavoritePage = async (favorite_url: string, page: number) => {
  return await request.post<FavoritePage>(
    '/bilibili/favorites/page',
    { favorite_url, page },
    { timeout: 30000 },
  ) as unknown as FavoritePage
}

export const startBilibiliFavoriteBatch = async (data: {
  favorite_folder: FavoriteBatchSnapshot['favorite_folder']
  videos: FavoriteVideo[]
  config: FavoriteBatchConfig
}) => {
  return await request.post<FavoriteBatchSnapshot>('/bilibili/favorites/batches', data) as unknown as FavoriteBatchSnapshot
}

export const getBilibiliFavoriteBatch = async (batchId: string) => {
  return await request.get<FavoriteBatchSnapshot>(`/bilibili/favorites/batches/${batchId}`, {
    suppressToast: true,
  }) as unknown as FavoriteBatchSnapshot
}

export const pauseBilibiliFavoriteBatch = async (batchId: string) => {
  return await request.post<FavoriteBatchSnapshot>(`/bilibili/favorites/batches/${batchId}/pause`) as unknown as FavoriteBatchSnapshot
}

export const resumeBilibiliFavoriteBatch = async (batchId: string) => {
  return await request.post<FavoriteBatchSnapshot>(`/bilibili/favorites/batches/${batchId}/resume`) as unknown as FavoriteBatchSnapshot
}

export const deleteBilibiliFavoriteBatch = async (batchId: string) => {
  return await request.delete(`/bilibili/favorites/batches/${batchId}`)
}
