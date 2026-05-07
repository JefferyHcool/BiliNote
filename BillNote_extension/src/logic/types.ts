// 与 backend/app/routers/note.py / provider.py / model.py 对齐
export type Platform = 'bilibili' | 'youtube' | 'douyin' | 'kuaishou' | 'local'
export type Quality = 'fast' | 'medium' | 'slow'

export type TaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'

export interface Provider {
  id: string
  name: string
  logo: string
  type: string
  enabled: number
  base_url?: string
  api_key?: string
}

export interface Model {
  id: string
  model_name: string
  provider_id: string
}

export interface GenerateRequest {
  video_url: string
  platform: Platform
  quality: Quality
  model_name: string
  provider_id: string
  screenshot?: boolean
  link?: boolean
  format?: string[]
  style?: string
  extras?: string
}

export interface NoteResult {
  markdown: string
  transcript?: unknown
  audio_meta?: {
    title?: string
    duration?: number
    cover_url?: string
    [k: string]: unknown
  }
}

export interface TaskStatusResponse {
  status: TaskStatus
  message: string
  task_id: string
  result?: NoteResult
}

export interface TaskRecord {
  taskId: string
  videoUrl: string
  platform: Platform
  status: TaskStatus
  message: string
  createdAt: number
  updatedAt: number
  result?: NoteResult
}

export interface Settings {
  backendUrl: string
  providerId: string
  modelName: string
  quality: Quality
  screenshot: boolean
  link: boolean
  style: string
}
