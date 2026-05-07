import { useWebExtensionStorage } from '~/composables/useWebExtensionStorage'
import type { Settings, TaskRecord } from './types'
import { DEFAULT_SETTINGS, MAX_TASKS, SETTINGS_KEY, TASKS_KEY } from './constants'

export { DEFAULT_BACKEND_URL, DEFAULT_SETTINGS, MAX_TASKS } from './constants'

// 全局共享设置（popup / options / sidepanel 三个 Vue 上下文都读这一份）
// 注意：background service worker 不要 import 这个文件，改用 chrome.storage 直读
export const { data: settings, dataReady: settingsReady } = useWebExtensionStorage<Settings>(
  SETTINGS_KEY,
  DEFAULT_SETTINGS,
  { mergeDefaults: true },
)

export const { data: tasks, dataReady: tasksReady } = useWebExtensionStorage<TaskRecord[]>(
  TASKS_KEY,
  [],
)

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
