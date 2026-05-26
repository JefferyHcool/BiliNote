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
  video_understanding?: boolean
  video_interval?: number
  grid_size?: [number, number]
  // 客户端在浏览器里直接抓到的字幕，跳过后端的 download_subtitles + 音频转写
  prefetched_transcript?: {
    language: string
    full_text: string
    segments: Array<{ start: number, end: number, text: string }>
    source?: string
  }
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
  // 从浏览器 tab.title 抓取，任务完成前用来替代 videoUrl 显示
  title?: string
}

// 与 backend/app/gpt/prompt_builder.py note_styles 一一对齐
export type NoteStyle =
  | 'minimal' | 'detailed' | 'academic' | 'tutorial'
  | 'xiaohongshu' | 'life_journal' | 'task_oriented'
  | 'business' | 'meeting_minutes'

// 与 backend/app/gpt/prompt_builder.py note_formats 一一对齐
export type NoteFormat = 'toc' | 'link' | 'screenshot' | 'summary'

export const NOTE_STYLES: Array<{ value: NoteStyle, label: string }> = [
  { value: 'minimal', label: '精简' },
  { value: 'detailed', label: '详细' },
  { value: 'tutorial', label: '教程' },
  { value: 'academic', label: '学术' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'life_journal', label: '生活向' },
  { value: 'task_oriented', label: '任务导向' },
  { value: 'business', label: '商业风格' },
  { value: 'meeting_minutes', label: '会议纪要' },
]

export const NOTE_FORMATS: Array<{ value: NoteFormat, label: string }> = [
  { value: 'toc', label: '目录' },
  { value: 'summary', label: 'AI 总结' },
  { value: 'screenshot', label: '原片截图' },
  { value: 'link', label: '原片跳转' },
]

export interface Settings {
  backendUrl: string
  providerId: string
  modelName: string
  quality: Quality
  // 输出 format 的 toggle 集合（screenshot / link 与下方两个布尔保持联动）
  formats: NoteFormat[]
  screenshot: boolean
  link: boolean
  style: NoteStyle
  extras: string
  // 多模态视频理解：抽帧拼图喂给视觉模型，提升画面相关问题的回答质量
  // 要求所选 model 是视觉模型（如 gpt-4o / gemini / claude-opus 系列），文字模型会忽略图片
  video_understanding: boolean
  // 抽帧间隔（秒），范围 1-30，默认 6
  video_interval: number
  // 拼图网格 [rows, cols]，每张拼图最多 rows*cols 帧。默认 [2,2]
  grid_size: [number, number]
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

