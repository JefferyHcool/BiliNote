import { useWebExtensionStorage } from '~/composables/useWebExtensionStorage'
import type { Settings, TaskRecord } from './types'

export const DEFAULT_BACKEND_URL = 'http://localhost:8483'

export const DEFAULT_SETTINGS: Settings = {
  backendUrl: DEFAULT_BACKEND_URL,
  providerId: '',
  modelName: '',
  quality: 'medium',
  screenshot: false,
  link: false,
  style: '',
}

// 全局共享设置（popup / options / sidepanel / background 都读这一份）
export const { data: settings, dataReady: settingsReady } = useWebExtensionStorage<Settings>(
  'bilinote-settings',
  DEFAULT_SETTINGS,
  { mergeDefaults: true },
)

// 历史任务列表，最近的在前
export const { data: tasks, dataReady: tasksReady } = useWebExtensionStorage<TaskRecord[]>(
  'bilinote-tasks',
  [],
)

export const MAX_TASKS = 30

export function upsertTask(record: TaskRecord) {
  const list = tasks.value ?? []
  const idx = list.findIndex(t => t.taskId === record.taskId)
  if (idx >= 0)
    list.splice(idx, 1, { ...list[idx], ...record })
  else
    list.unshift(record)
  tasks.value = list.slice(0, MAX_TASKS)
}

export function removeTask(taskId: string) {
  const list = tasks.value ?? []
  tasks.value = list.filter(t => t.taskId !== taskId)
}
