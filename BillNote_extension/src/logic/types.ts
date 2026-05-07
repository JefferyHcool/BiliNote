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

export interface ProviderUpdatePayload {
  id: string
  name?: string
  api_key?: string
  base_url?: string
  type?: string
  enabled?: number
}

export interface ProviderCreatePayload {
  name: string
  api_key: string
  base_url: string
  type: string
  logo?: string
}

export type TranscriberType = 'fast-whisper' | 'bcut' | 'kuaishou' | 'groq' | 'mlx-whisper'
export type WhisperModelSize = 'tiny' | 'base' | 'small' | 'medium' | 'large-v3' | 'large-v3-turbo'

export interface TranscriberOption {
  value: TranscriberType
  label: string
}

export interface TranscriberConfig {
  transcriber_type: TranscriberType
  whisper_model_size: WhisperModelSize | null
  available_types: TranscriberOption[]
  whisper_model_sizes: WhisperModelSize[]
  mlx_whisper_available: boolean
}

export interface WhisperModelStatus {
  model_size: WhisperModelSize
  downloaded: boolean
  downloading: boolean
}

export interface TranscriberModelsStatus {
  whisper: WhisperModelStatus[]
  mlx_whisper: WhisperModelStatus[]
  mlx_available: boolean
}

export interface DeployStatus {
  backend: { status: string, port: number }
  cuda: { available: boolean, version: string | null, gpu_name: string | null }
  whisper: { model_size: string, transcriber_type: string }
  ffmpeg: { available: boolean }
}

