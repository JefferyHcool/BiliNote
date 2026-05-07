// 在浏览器里直接调 B 站 player API 抓字幕。
// 因为 manifest host_permissions: '*://*/*' 覆盖 api.bilibili.com，service worker 里的
// fetch 会自动带 .bilibili.com 域下的用户 cookie，并且绕过 CORS——AI 字幕需要登录态，
// 这等于用用户当前浏览器的登录身份代替了 backend 那边的 SESSDATA 配置。
//
// 与 backend/app/downloaders/bilibili_subtitle.py 的 BilibiliSubtitleFetcher 行为对齐。

const UA
  = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

export interface PrefetchedTranscript {
  language: string
  full_text: string
  segments: Array<{ start: number, end: number, text: string }>
  source: 'bilibili_extension'
}

interface SubtitleEntry {
  lan?: string
  ai_type?: number
  subtitle_url?: string
}

function extractBvid(url: string): string | null {
  const m = url.match(/BV([0-9A-Za-z]+)/)
  return m ? `BV${m[1]}` : null
}

async function jsonGet<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, {
      credentials: 'include',
      headers: { 'User-Agent': UA, 'Referer': 'https://www.bilibili.com' },
    })
    if (!res.ok)
      return null
    return await res.json() as T
  }
  catch (e) {
    console.warn('[bilinote] B 站 API 请求失败:', url, e)
    return null
  }
}

async function getCid(bvid: string): Promise<number | null> {
  const data = await jsonGet<{ code: number, data?: { cid?: number } }>(
    `https://api.bilibili.com/x/web-interface/view?bvid=${bvid}`,
  )
  if (!data || data.code !== 0)
    return null
  return data.data?.cid ?? null
}

async function listSubtitles(bvid: string, cid: number): Promise<SubtitleEntry[]> {
  const data = await jsonGet<{
    code: number
    data?: { subtitle?: { subtitles?: SubtitleEntry[] } }
  }>(`https://api.bilibili.com/x/player/wbi/v2?bvid=${bvid}&cid=${cid}`)
  if (!data || data.code !== 0)
    return []
  return data.data?.subtitle?.subtitles ?? []
}

function pickSubtitle(subtitles: SubtitleEntry[]): SubtitleEntry | null {
  if (!subtitles.length)
    return null
  const isZh = (s: SubtitleEntry) => {
    const lan = (s.lan || '').toLowerCase()
    return lan.startsWith('zh') || lan === 'ai-zh'
  }
  // 优先级：人工中文 > AI 中文 > 任意非空
  return (
    subtitles.find(s => isZh(s) && !s.ai_type)
    || subtitles.find(s => isZh(s))
    || subtitles[0]
  )
}

function normalizeUrl(url: string): string {
  return url.startsWith('//') ? `https:${url}` : url
}

interface SubtitleBody {
  body?: Array<{ from?: number, to?: number, content?: string }>
}

export async function fetchBilibiliSubtitle(videoUrl: string): Promise<PrefetchedTranscript | null> {
  const bvid = extractBvid(videoUrl)
  if (!bvid)
    return null

  const cid = await getCid(bvid)
  if (!cid)
    return null

  const subtitles = await listSubtitles(bvid, cid)
  const track = pickSubtitle(subtitles)
  if (!track?.subtitle_url) {
    console.info(`[bilinote] B 站 ${bvid} 没找到可用字幕轨（可能未登录或视频无字幕）`)
    return null
  }

  const sub = await jsonGet<SubtitleBody>(normalizeUrl(track.subtitle_url))
  const body = sub?.body || []
  const segments: PrefetchedTranscript['segments'] = []
  for (const item of body) {
    const text = (item.content || '').trim()
    if (!text)
      continue
    segments.push({
      start: Number(item.from || 0),
      end: Number(item.to || 0),
      text,
    })
  }
  if (!segments.length)
    return null

  return {
    language: track.lan || 'zh',
    full_text: segments.map(s => s.text).join(' '),
    segments,
    source: 'bilibili_extension',
  }
}
