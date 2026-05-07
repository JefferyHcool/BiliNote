import type { Platform } from './types'

// 与 backend/app/validators/video_url_validator.py 保持一致
export function detectPlatform(url: string | undefined | null): Platform | null {
  if (!url)
    return null
  if (/bilibili\.com\/video\//.test(url))
    return 'bilibili'
  if (/(youtube\.com\/watch|youtu\.be\/)/.test(url))
    return 'youtube'
  if (url.includes('douyin'))
    return 'douyin'
  if (url.includes('kuaishou'))
    return 'kuaishou'
  return null
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  bilibili: '哔哩哔哩',
  youtube: 'YouTube',
  douyin: '抖音',
  kuaishou: '快手',
  local: '本地',
}
