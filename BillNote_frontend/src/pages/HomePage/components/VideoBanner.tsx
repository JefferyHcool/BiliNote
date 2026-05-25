import { ExternalLink } from 'lucide-react'
import type { AudioMeta } from '@/store/taskStore'

interface VideoBannerProps {
  audioMeta?: AudioMeta
  videoUrl?: string
}

/** 平台 label 映射 */
const platformLabel: Record<string, string> = {
  bilibili: '哔哩哔哩',
  youtube: 'YouTube',
  douyin: '抖音',
  xiaohongshu: '小红书',
}

export default function VideoBanner({ audioMeta, videoUrl }: VideoBannerProps) {
  if (!audioMeta) return null

  const rawCover = audioMeta.cover_url
  // 通过后端代理加载封面，避免跨域/Referrer 限制
  const apiBase = String(import.meta.env.VITE_API_BASE_URL || 'api').replace(/\/$/, '')
  const coverUrl = rawCover ? `${apiBase}/image_proxy?url=${encodeURIComponent(rawCover)}` : ''
  const title = audioMeta.title
  const uploader = audioMeta.raw_info?.uploader || ''
  const platform = platformLabel[audioMeta.platform] || audioMeta.platform || ''
  const originalUrl = videoUrl || audioMeta.raw_info?.webpage_url || ''

  return (
    <div className="relative mb-4 overflow-hidden rounded-lg">
      {/* 模糊背景封面 */}
      <div className="absolute inset-0">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt=""
            referrerPolicy="no-referrer"
            className="h-full w-full scale-110 object-cover blur-md brightness-[0.4]"
          />
        ) : (
          <div className="h-full w-full bg-gradient-to-r from-blue-600 to-indigo-700" />
        )}
      </div>

      {/* 内容层 */}
      <div className="relative flex min-w-0 flex-wrap items-center gap-3 px-3 py-3 sm:gap-4 sm:px-5 sm:py-4">
        {/* 封面缩略图 */}
        {coverUrl && (
          <img
            src={coverUrl}
            alt={title}
            referrerPolicy="no-referrer"
            className="h-14 w-24 shrink-0 rounded-md object-cover shadow-md"
          />
        )}

        {/* 文字信息 */}
        <div className="min-w-0 flex-[1_1_12rem]">
          <h2
            className="line-clamp-2 text-sm font-bold [overflow-wrap:anywhere] break-words text-white sm:text-base"
            title={title}
          >
            {title}
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs [overflow-wrap:anywhere] break-words text-white/70 sm:text-sm">
            {uploader && (
              <span className="min-w-0 [overflow-wrap:anywhere] break-words">{uploader}</span>
            )}
            {uploader && platform && <span className="text-white/40">·</span>}
            {platform && (
              <span className="min-w-0 [overflow-wrap:anywhere] break-words">{platform}</span>
            )}
          </div>
        </div>

        {/* 跳转原视频 */}
        {originalUrl && (
          <a
            href={originalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex shrink-0 items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs font-medium text-white backdrop-blur-sm transition-colors hover:bg-white/25 sm:px-3 sm:py-1.5"
          >
            <ExternalLink className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
            <span className="hidden sm:inline">原视频</span>
          </a>
        )}
      </div>
    </div>
  )
}
