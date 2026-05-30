import { storage } from 'webextension-polyfill'
import { DEFAULT_SETTINGS, DELETED_TASK_IDS_KEY, MAX_TASKS, SETTINGS_KEY, TASKS_KEY } from './constants'
import type { Settings, TaskRecord } from './types'
import { useWebExtensionStorage } from '~/composables/useWebExtensionStorage'

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
  // 任务历史是可删除数据；不要在读不到 key 时自动写入 []，避免多个扩展页面并发打开时用空数组覆盖旧历史。
  { writeDefaults: false },
)

const MAX_DELETED_TASK_IDS = 200

let taskMutationQueue = Promise.resolve()

function parseJsonValue<T>(value: unknown, fallback: T): T {
  if (value == null)
    return fallback
  if (typeof value !== 'string')
    return value as T
  try {
    return JSON.parse(value) as T
  }
  catch {
    return fallback
  }
}

async function readJson<T>(key: string, fallback: T): Promise<T> {
  const obj = await storage.local.get(key)
  return parseJsonValue(obj[key], fallback)
}

function normalizeTasks(value: unknown): TaskRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is TaskRecord => !!item && typeof item === 'object' && typeof (item as TaskRecord).taskId === 'string')
    : []
}

async function readPersistedTasks(): Promise<TaskRecord[]> {
  return normalizeTasks(await readJson<unknown>(TASKS_KEY, []))
}

export async function readDeletedTaskIds(): Promise<string[]> {
  const ids = await readJson<unknown>(DELETED_TASK_IDS_KEY, [])
  return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : []
}

function mergeTasks(...sources: Array<TaskRecord[] | undefined>): TaskRecord[] {
  const map = new Map<string, TaskRecord>()
  for (const source of sources) {
    for (const task of source ?? []) {
      const existing = map.get(task.taskId)
      if (!existing || (task.updatedAt || task.createdAt || 0) >= (existing.updatedAt || existing.createdAt || 0))
        map.set(task.taskId, { ...existing, ...task })
    }
  }
  return Array.from(map.values()).sort((a, b) => (b.updatedAt || b.createdAt || 0) - (a.updatedAt || a.createdAt || 0))
}

function enqueueTaskMutation(mutator: (list: TaskRecord[], deletedIds: Set<string>) => TaskRecord[] | Promise<TaskRecord[]>) {
  const run = taskMutationQueue
    .catch(() => {})
    .then(async () => {
      const [persistedTasks, deletedTaskIds] = await Promise.all([
        readPersistedTasks(),
        readDeletedTaskIds(),
      ])
      const deletedIds = new Set(deletedTaskIds)
      const base = mergeTasks(persistedTasks, tasks.value).filter(task => !deletedIds.has(task.taskId))
      const next = (await mutator(base, deletedIds))
        .filter(task => !deletedIds.has(task.taskId))
        .slice(0, MAX_TASKS)
      tasks.value = next
      await storage.local.set({ [TASKS_KEY]: JSON.stringify(next) })
      return next
    })

  taskMutationQueue = run.then(() => undefined, () => undefined)
  return run
}

export async function isTaskDeleted(taskId: string): Promise<boolean> {
  return (await readDeletedTaskIds()).includes(taskId)
}

export function upsertTask(record: TaskRecord) {
  return enqueueTaskMutation((list, deletedIds) => {
    // 用户已经手动删除的任务，不允许被后端同步/旧 popup/轮询再写回历史。
    if (deletedIds.has(record.taskId))
      return list

    const next = [...list]
    const idx = next.findIndex(t => t.taskId === record.taskId)
    if (idx >= 0)
      next.splice(idx, 1, { ...next[idx], ...record })
    else
      next.unshift(record)

    return next
  })
}

export function removeTask(taskId: string) {
  const run = taskMutationQueue
    .catch(() => {})
    .then(async () => {
      const [persistedTasks, deletedTaskIds] = await Promise.all([
        readPersistedTasks(),
        readDeletedTaskIds(),
      ])
      const nextDeletedTaskIds = [
        taskId,
        ...deletedTaskIds.filter(id => id !== taskId),
      ].slice(0, MAX_DELETED_TASK_IDS)
      const deletedIds = new Set(nextDeletedTaskIds)
      // 删除以当前界面看到的列表为准；若 storage 里还有旧快照，不要把旧任务合并回来。
      const visibleTasks = normalizeTasks(tasks.value)
      const baseTasks = visibleTasks.length > 0 ? visibleTasks : persistedTasks
      const nextTasks = mergeTasks(baseTasks)
        .filter(task => !deletedIds.has(task.taskId))
        .slice(0, MAX_TASKS)

      tasks.value = nextTasks
      await storage.local.set({
        [DELETED_TASK_IDS_KEY]: JSON.stringify(nextDeletedTaskIds),
        [TASKS_KEY]: JSON.stringify(nextTasks),
      })
      return nextTasks
    })

  taskMutationQueue = run.then(() => undefined, () => undefined)
  return run
}

export function forgetDeletedTaskId(taskId: string) {
  return taskMutationQueue
    .catch(() => {})
    .then(async () => {
      const deletedTaskIds = await readDeletedTaskIds()
      await storage.local.set({
        [DELETED_TASK_IDS_KEY]: JSON.stringify(deletedTaskIds.filter(id => id !== taskId)),
      })
    })
}
