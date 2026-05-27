import { ExternalLink, MessageSquare, PlaySquare } from 'lucide-react'
import type { AudioMeta } from '@/store/taskStore'
import { withAuthTokenQuery } from '@/services/auth'

interface VideoBannerProps {
  audioMeta?: AudioMeta
  videoUrl?: string
}

const toTextArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value
      .map(item => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>
          return String(record.name || record.tag_name || record.title || '').trim()
        }
        return ''
      })
      .filter(Boolean)
  }

  if (typeof value === 'string') {
    return value
      .split(/[,，#\s]+/)
      .map(item => item.trim())
      .filter(Boolean)
  }

  return []
}

const formatCount = (value: unknown) => {
  const num = Number(value)
  if (!Number.isFinite(num) || num <= 0) return ''
  if (num >= 100000000) return `${(num / 100000000).toFixed(1).replace(/\.0$/, '')}亿`
  if (num >= 10000) return `${(num / 10000).toFixed(1).replace(/\.0$/, '')}万`
  return `${num}`
}

const formatDuration = (value: unknown) => {
  const rawSeconds = Number(value)
  if (!Number.isFinite(rawSeconds) || rawSeconds <= 0) return ''
  const seconds = rawSeconds > 86400 ? rawSeconds / 1000 : rawSeconds
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

const firstNumber = (...values: unknown[]) => {
  for (const value of values) {
    const num = Number(value)
    if (Number.isFinite(num) && num > 0) return num
  }
  return undefined
}

const firstText = (...values: unknown[]) => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return ''
}

const parsePublishTime = (...values: unknown[]) => {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
      const milliseconds = value > 100000000000 ? value : value * 1000
      return new Date(milliseconds)
    }

    if (typeof value === 'string' && value.trim()) {
      const text = value.trim()
      if (/^\d{8}$/.test(text)) {
        return new Date(`${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}T00:00:00`)
      }

      const milliseconds = Date.parse(text)
      if (!Number.isNaN(milliseconds)) return new Date(milliseconds)
    }
  }

  return null
}

const formatPublishTime = (date: Date | null) => {
  if (!date || Number.isNaN(date.getTime())) return ''
  return date
    .toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
    .replace(/\//g, '-')
}

export default function VideoBanner({ audioMeta, videoUrl }: VideoBannerProps) {
  if (!audioMeta) return null

  const rawCover = audioMeta.cover_url
  // 通过后端代理加载封面，避免跨域/Referrer 限制
  const apiBase = String(import.meta.env.VITE_API_BASE_URL || 'api').replace(/\/$/, '')
  const coverUrl = rawCover
    ? withAuthTokenQuery(`${apiBase}/image_proxy?url=${encodeURIComponent(rawCover)}`)
    : ''
  const title = audioMeta.title
  const rawInfo = audioMeta.raw_info || {}
  const uploader = firstText(
    rawInfo.uploader ||
      rawInfo.author_name ||
      rawInfo.owner?.name ||
      rawInfo.user?.nickname ||
      rawInfo.author?.name ||
      rawInfo.author
  )
  const originalUrl = videoUrl || rawInfo.webpage_url || rawInfo.original_url || ''
  const tags = toTextArray(rawInfo.tags || rawInfo.tag || rawInfo.keywords).slice(0, 6)
  const description = String(
    rawInfo.description || rawInfo.desc || rawInfo.caption || rawInfo.dynamic || ''
  ).trim()
  const fanCount = formatCount(
    rawInfo.uploader_subscriber_count ||
      rawInfo.channel_follower_count ||
      rawInfo.follower_count ||
      rawInfo.fans ||
      rawInfo.owner?.fans ||
      rawInfo.author?.follower_count
  )
  const publishTime = formatPublishTime(
    parsePublishTime(
      rawInfo.timestamp,
      rawInfo.release_timestamp,
      rawInfo.pubdate,
      rawInfo.publish_time,
      rawInfo.upload_date,
      rawInfo.create_time,
      rawInfo.created_at,
      rawInfo.photo?.timestamp
    )
  )
  const viewCount = formatCount(
    firstNumber(
      rawInfo.view_count,
      rawInfo.play_count,
      rawInfo.stat?.view,
      rawInfo.statistics?.view_count,
      rawInfo.photo?.viewCount
    )
  )
  const commentCount = formatCount(
    firstNumber(
      rawInfo.comment_count,
      rawInfo.comments_count,
      rawInfo.stat?.reply,
      rawInfo.statistics?.comment_count,
      rawInfo.photo?.commentCount
    )
  )
  const duration = formatDuration(audioMeta.duration || rawInfo.duration || rawInfo.photo?.duration)

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
      <div className="relative flex min-w-0 items-stretch gap-3 px-3 py-3 sm:gap-4 sm:px-5 sm:py-4">
        {/* 封面缩略图 */}
        {coverUrl &&
          (originalUrl ? (
            <a
              href={originalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="group relative h-24 w-40 shrink-0 overflow-hidden rounded-md shadow-md sm:h-32 sm:w-56"
              title="打开原视频"
            >
              <img
                src={coverUrl}
                alt={title}
                referrerPolicy="no-referrer"
                className="h-full w-full object-cover transition-transform group-hover:scale-105"
              />
              <span className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/75 via-black/35 to-transparent" />
              <span className="absolute top-1 right-1 rounded-full bg-black/45 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100">
                <ExternalLink className="h-3 w-3" />
              </span>
              <div className="absolute right-1.5 bottom-1.5 left-1.5 flex items-end justify-between gap-2 text-[11px] font-medium text-white drop-shadow-sm sm:text-xs">
                <div className="flex min-w-0 items-center gap-2">
                  {viewCount && (
                    <span className="inline-flex items-center gap-1">
                      <PlaySquare className="h-3.5 w-3.5" />
                      {viewCount}
                    </span>
                  )}
                  {commentCount && (
                    <span className="inline-flex items-center gap-1">
                      <MessageSquare className="h-3.5 w-3.5" />
                      {commentCount}
                    </span>
                  )}
                </div>
                {duration && <span className="shrink-0">{duration}</span>}
              </div>
            </a>
          ) : (
            <img
              src={coverUrl}
              alt={title}
              referrerPolicy="no-referrer"
              className="h-24 w-40 shrink-0 rounded-md object-cover shadow-md sm:h-32 sm:w-56"
            />
          ))}

        {/* 文字信息 */}
        <div className="flex min-w-0 flex-1 flex-col justify-center py-1">
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
            {fanCount && (
              <>
                {uploader && <span className="text-white/40">·</span>}
                <span className="shrink-0">{fanCount}粉丝</span>
              </>
            )}
            {publishTime && (
              <>
                {(uploader || fanCount) && <span className="text-white/40">·</span>}
                <span className="shrink-0">发布于 {publishTime}</span>
              </>
            )}
          </div>

          {tags.length > 0 && (
            <div className="mt-1 flex max-w-full gap-1 overflow-hidden">
              {tags.map(tag => (
                <span
                  key={tag}
                  className="max-w-[7rem] shrink-0 truncate rounded-full bg-white/15 px-2 py-0.5 text-[11px] text-white/85"
                  title={tag}
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}

          {description && (
            <p className="mt-1 line-clamp-1 text-xs text-white/60" title={description}>
              {description}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
