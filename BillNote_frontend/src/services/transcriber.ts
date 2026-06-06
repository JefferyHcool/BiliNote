import request from '@/utils/request'

export interface TranscriberConfig {
  transcriber_type: string
  whisper_model_size: string
  available_types: { value: string; label: string }[]
  whisper_model_sizes: string[]
  /** 内置模型映射：size → HF repo_id */
  whisper_builtin_models?: Record<string, string>
  /** 用户自定义模型映射：名称 → HF repo_id 或本地路径 */
  whisper_custom_models?: Record<string, string>
  mlx_whisper_available: boolean
}

export interface ModelStatus {
  model_size: string
  downloaded: boolean
  downloading: boolean
}

export interface ModelsStatusResponse {
  whisper: ModelStatus[]
  mlx_whisper: ModelStatus[]
  mlx_available: boolean
}

export const getTranscriberConfig = async (): Promise<TranscriberConfig> => {
  return await request.get('/transcriber_config')
}

export const updateTranscriberConfig = async (data: {
  transcriber_type: string
  whisper_model_size?: string
}) => {
  return await request.post('/transcriber_config', data)
}

export const getModelsStatus = async (): Promise<ModelsStatusResponse> => {
  return await request.get('/transcriber_models_status')
}

export const downloadModel = async (data: {
  model_size: string
  transcriber_type?: string
}) => {
  return await request.post('/transcriber_download', data)
}

export interface WhisperModelsResponse {
  builtin: Record<string, string>
  custom: Record<string, string>
}

/** 列出内置 + 自定义 whisper 模型映射 */
export const listWhisperModels = async (): Promise<WhisperModelsResponse> => {
  return await request.get('/whisper_models')
}

/** 新增自定义模型映射（名称 → HF repo_id 或本地路径） */
export const addWhisperModel = async (data: { name: string; target: string }) => {
  return await request.post('/whisper_models', data)
}

/** 删除自定义模型映射（不会删除已下载的模型文件） */
export const deleteWhisperModel = async (name: string) => {
  return await request.delete(`/whisper_models/${encodeURIComponent(name)}`)
}
