import type { TaskRecord } from './types'

const SITE_SUFFIX_RE = /\s*[-_—–|｜]\s*(哔哩哔哩|bilibili|youtube|抖音|douyin|快手|kuaishou)\s*$/i

export function normalizeVideoTitle(title: string | undefined | null): string | undefined {
  const value = title?.trim()
  if (!value)
    return undefined
  return value
    .replace(SITE_SUFFIX_RE, '')
    .trim() || value
}

export function getTaskDisplayTitle(task: TaskRecord | undefined | null, fallbackTitle?: string): string {
  if (!task)
    return normalizeVideoTitle(fallbackTitle) || ''
  return normalizeVideoTitle((task.result?.audio_meta as { title?: string } | undefined)?.title)
    || normalizeVideoTitle(task.title)
    || normalizeVideoTitle(fallbackTitle)
    || task.videoUrl
}
