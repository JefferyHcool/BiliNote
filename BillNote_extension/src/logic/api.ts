import type { GenerateRequest, Model, Provider, TaskStatusResponse } from './types'
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
  return request<Model[]>(`/api/get_models_by_provider/${providerId}`)
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
