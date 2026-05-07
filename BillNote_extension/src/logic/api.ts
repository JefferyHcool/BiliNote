import type {
  DeployStatus,
  GenerateRequest,
  Model,
  Provider,
  ProviderCreatePayload,
  ProviderUpdatePayload,
  TaskStatusResponse,
  TranscriberConfig,
  TranscriberModelsStatus,
  TranscriberType,
  WhisperModelSize,
} from './types'
import { settings } from './storage'

interface ApiEnvelope<T> {
  code: number
  msg: string
  data: T
}

function backendUrl(): string {
  return (settings.value?.backendUrl || 'http://localhost:8483').replace(/\/$/, '')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${backendUrl()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok)
    throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  const body = (await res.json()) as ApiEnvelope<T> | T
  // 后端 ResponseWrapper 包了 {code, msg, data}；非 0 视为业务错
  if (body && typeof body === 'object' && 'code' in body) {
    const env = body as ApiEnvelope<T>
    if (env.code !== 0)
      throw new Error(env.msg || '后端返回失败')
    return env.data
  }
  return body as T
}

export async function getProviders(): Promise<Provider[]> {
  return request<Provider[]>('/api/get_all_providers')
}

export async function getModelsByProvider(providerId: string): Promise<Model[]> {
  return request<Model[]>(`/api/model_enable/${providerId}`)
}

export async function setDownloaderCookie(platform: string, cookie: string): Promise<void> {
  await request('/api/update_downloader_cookie', {
    method: 'POST',
    body: JSON.stringify({ platform, cookie }),
  })
}

export async function getDownloaderCookie(platform: string): Promise<string | null> {
  // 后端：未配置时返回 {code:0, msg:'未找到Cookies', data:null}；配置时 data: {platform, cookie}
  const data = await request<{ platform: string, cookie: string } | null>(
    `/api/get_downloader_cookie/${platform}`,
  )
  return data?.cookie ?? null
}

// ---- Provider CRUD ----
export async function addProvider(payload: ProviderCreatePayload): Promise<string | null> {
  return request<string | null>('/api/add_provider', {
    method: 'POST',
    body: JSON.stringify({ logo: 'custom', ...payload }),
  })
}

export async function updateProvider(payload: ProviderUpdatePayload): Promise<{ id: string, enabled: number }> {
  return request<{ id: string, enabled: number }>('/api/update_provider', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getProviderById(id: string): Promise<Provider> {
  return request<Provider>(`/api/get_provider_by_id/${id}`)
}

export async function connectTest(id: string): Promise<void> {
  await request('/api/connect_test', {
    method: 'POST',
    body: JSON.stringify({ id }),
  })
}

// ---- Model CRUD ----
export async function listAllModels(providerId: string): Promise<Model[]> {
  return request<Model[]>(`/api/model_list/${providerId}`)
}

export async function addModel(providerId: string, modelName: string): Promise<void> {
  await request('/api/models', {
    method: 'POST',
    body: JSON.stringify({ provider_id: providerId, model_name: modelName }),
  })
}

export async function deleteModel(modelId: number | string): Promise<void> {
  await request(`/api/models/delete/${modelId}`)
}

// ---- Transcriber ----
export async function getTranscriberConfig(): Promise<TranscriberConfig> {
  return request<TranscriberConfig>('/api/transcriber_config')
}

export async function setTranscriberConfig(transcriberType: TranscriberType, whisperModelSize?: WhisperModelSize): Promise<TranscriberConfig> {
  return request<TranscriberConfig>('/api/transcriber_config', {
    method: 'POST',
    body: JSON.stringify({
      transcriber_type: transcriberType,
      whisper_model_size: whisperModelSize ?? null,
    }),
  })
}

export async function getTranscriberModelsStatus(): Promise<TranscriberModelsStatus> {
  return request<TranscriberModelsStatus>('/api/transcriber_models_status')
}

export async function downloadTranscriberModel(modelSize: WhisperModelSize, transcriberType: TranscriberType = 'fast-whisper'): Promise<void> {
  await request('/api/transcriber_download', {
    method: 'POST',
    body: JSON.stringify({ model_size: modelSize, transcriber_type: transcriberType }),
  })
}

// ---- Monitor ----
export async function getDeployStatus(): Promise<DeployStatus> {
  return request<DeployStatus>('/api/deploy_status')
}

export async function getSysHealth(): Promise<{ ok: boolean, msg?: string }> {
  try {
    await request('/api/sys_health')
    return { ok: true }
  }
  catch (e) {
    return { ok: false, msg: (e as Error).message }
  }
}

export async function generateNote(payload: GenerateRequest): Promise<{ task_id: string }> {
  return request<{ task_id: string }>('/api/generate_note', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  // /task_status/{id} 返回的是裸对象（非 ResponseWrapper 包装），见 routers/note.py
  const res = await fetch(`${backendUrl()}/api/task_status/${taskId}`)
  if (!res.ok)
    throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as TaskStatusResponse
}

export async function ping(): Promise<boolean> {
  try {
    await getProviders()
    return true
  }
  catch {
    return false
  }
}

// markdown 里的 /static/screenshots/xxx 是相对路径，extension 渲染时需要拼绝对地址
export function absolutizeMarkdownImages(md: string): string {
  const base = backendUrl()
  return md.replace(/!\[([^\]]*)\]\((\/static\/[^)]+)\)/g, (_, alt, path) => `![${alt}](${base}${path})`)
}
