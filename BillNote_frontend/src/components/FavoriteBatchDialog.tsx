import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, Check, Loader2, ListVideo, Pause, Play, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  deleteBilibiliFavoriteBatch,
  getBilibiliFavoriteBatch,
  getBilibiliFavoritePage,
  pauseBilibiliFavoriteBatch,
  resumeBilibiliFavoriteBatch,
  startBilibiliFavoriteBatch,
  type FavoriteBatchSnapshot,
  type FavoriteVideo,
} from '@/services/favorites'
import type { GenerateNotePayload } from '@/services/note'
import { useTaskStore, type FavoriteFolderInfo, type FavoriteVideoInfo } from '@/store/taskStore'

const STORAGE_KEY = 'bilinote-favorite-batch-v1'
type BatchState = 'idle' | 'running' | 'paused' | 'done'
type GenerationConfig = Omit<GenerateNotePayload, 'video_url' | 'platform' | 'task_id'>

interface SavedBatch {
  batchId: string | null
  favoriteUrl: string
  favoriteId: string
  favoriteTitle: string
  videos: FavoriteVideo[]
  selectedBvids: string[]
  page: number
  total: number
  hasMore: boolean
  config: GenerationConfig | null
  nextIndex: number
  state: BatchState
}

interface BatchError {
  code?: number
  message?: string
  msg?: string
  data?: {
    reason?: string
    downloading?: boolean
  }
}

interface FavoriteBatchDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  getGenerationConfig: () => GenerationConfig | null
}

const getVideoKey = (video: FavoriteVideo) => {
  if (video.video_key) return video.video_key
  if ((video.page_count || 1) > 1) return `${video.bvid}_p${video.page_number || 1}`
  return video.bvid
}

const delay = (milliseconds: number) => new Promise(resolve => setTimeout(resolve, milliseconds))

const FavoriteBatchDialog = ({ open, onOpenChange, getGenerationConfig }: FavoriteBatchDialogProps) => {
  const addPendingTask = useTaskStore(state => state.addPendingTask)
  const [hydrated, setHydrated] = useState(false)
  const [favoriteUrl, setFavoriteUrl] = useState('')
  const [favoriteId, setFavoriteId] = useState('')
  const [favoriteTitle, setFavoriteTitle] = useState('')
  const [videos, setVideos] = useState<FavoriteVideo[]>([])
  const [selectedBvids, setSelectedBvids] = useState<string[]>([])
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingAll, setLoadingAll] = useState(false)
  const [batchSubmitting, setBatchSubmitting] = useState(false)
  const [batchState, setBatchState] = useState<BatchState>('idle')
  const [pauseRequested, setPauseRequested] = useState(false)
  const [batchId, setBatchId] = useState<string | null>(null)
  const [batchConfig, setBatchConfig] = useState<GenerationConfig | null>(null)
  const [nextIndex, setNextIndex] = useState(0)
  const [error, setError] = useState('')
  const hasMoreRef = useRef(false)
  const pageRef = useRef(0)

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const batch = JSON.parse(saved) as SavedBatch
        setBatchId(batch.batchId || null)
        setFavoriteUrl(batch.favoriteUrl || '')
        setFavoriteId(batch.favoriteId || '')
        setFavoriteTitle(batch.favoriteTitle || '')
        setVideos(batch.videos || [])
        setSelectedBvids(batch.selectedBvids || [])
        setPage(batch.page || 0)
        setTotal(batch.total || 0)
        setHasMore(Boolean(batch.hasMore))
        setBatchConfig(batch.config || null)
        setNextIndex(batch.nextIndex || 0)
        setBatchState(batch.state === 'running' && !batch.batchId ? 'paused' : batch.state || 'idle')
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    } finally {
      setHydrated(true)
    }
  }, [])

  useEffect(() => {
    pageRef.current = page
    hasMoreRef.current = hasMore
  }, [page, hasMore, selectedBvids, videos])

  useEffect(() => {
    if (!hydrated) return
    const saved: SavedBatch = {
      batchId,
      favoriteUrl,
      favoriteId,
      favoriteTitle,
      videos,
      selectedBvids,
      page,
      total,
      hasMore,
      config: batchConfig,
      nextIndex,
      state: batchState,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
  }, [hydrated, batchId, favoriteUrl, favoriteId, favoriteTitle, videos, selectedBvids, page, total, hasMore, batchConfig, nextIndex, batchState])

  const fetchPage = async (pageNumber: number, replace = false) => {
    const result = await getBilibiliFavoritePage(favoriteUrl, pageNumber)
    setFavoriteId(result.favorite_id)
    pageRef.current = result.page
    hasMoreRef.current = result.has_more
    setFavoriteTitle(result.title)
    setTotal(result.media_count)
    setPage(result.page)
    setHasMore(result.has_more)
    setVideos(current => {
      const existing = new Set(replace ? [] : current.map(getVideoKey))
      const incoming = result.videos.filter(video => !existing.has(getVideoKey(video)))
      return replace ? result.videos : [...current, ...incoming]
    })
    setSelectedBvids(current => {
      const base = replace ? [] : current
      return [...new Set([...base, ...result.videos.map(getVideoKey)])]
    })
  }

  const previewFavorite = async () => {
    if (!favoriteUrl.trim()) {
      setError('请粘贴 Bilibili 收藏夹链接')
      return
    }
    setLoading(true)
    setError('')
    setVideos([])
    setSelectedBvids([])
    setFavoriteId('')
    setPage(0)
    setBatchState('idle')
    if (batchId) void deleteBilibiliFavoriteBatch(batchId).catch(() => undefined)
    setBatchId(null)
    setBatchConfig(null)
    setNextIndex(0)
    try {
      await fetchPage(1, true)
    } catch (cause: unknown) {
      const failure = cause as BatchError
      setError(failure?.msg || failure?.message || '无法读取收藏夹，请检查 Cookie 和链接')
    } finally {
      setLoading(false)
    }
  }

  const loadAllPages = async () => {
    setLoadingAll(true)
    setError('')
    try {
      let nextPage = pageRef.current + 1
      while (hasMoreRef.current) {
        await delay(200)
        await fetchPage(nextPage)
        nextPage += 1
      }
    } catch (cause: unknown) {
      const failure = cause as BatchError
      setError(failure?.msg || failure?.message || '加载收藏夹后续视频失败')
    } finally {
      setLoadingAll(false)
    }
  }

  const applyBatchSnapshot = useCallback((snapshot: FavoriteBatchSnapshot) => {
    setBatchId(snapshot.batch_id)
    setFavoriteId(snapshot.favorite_folder.id)
    setFavoriteTitle(snapshot.favorite_folder.title)
    setFavoriteUrl(snapshot.favorite_folder.url)
    setBatchConfig(snapshot.config as GenerationConfig)
    setNextIndex(snapshot.next_index)
    setPauseRequested(snapshot.pause_requested)
    setBatchState(snapshot.state === 'failed' ? 'done' : snapshot.state)

    const snapshotVideos = new Map(snapshot.videos.map(video => [getVideoKey(video), video]))
    setVideos(current => current.map(video => {
      const serverVideo = snapshotVideos.get(getVideoKey(video))
      return serverVideo ? { ...video, ...serverVideo } : video
    }))

    const folder: FavoriteFolderInfo = snapshot.favorite_folder
    const existingTaskIds = new Set(useTaskStore.getState().tasks.map(task => task.id))
    for (const video of snapshot.videos) {
      if (!video.task_id || video.status === 'queued' || existingTaskIds.has(video.task_id)) continue
      const payload: GenerateNotePayload = {
        ...snapshot.config,
        style: snapshot.config.style || 'minimal',
        format: snapshot.config.format || [],
        grid_size: snapshot.config.grid_size || [],
        video_url: video.video_url,
        platform: 'bilibili',
      }
      const favoriteVideo: FavoriteVideoInfo = {
        bvid: video.bvid,
        title: video.title,
        page_number: video.page_number,
        page_count: video.page_count,
      }
      addPendingTask(video.task_id, 'bilibili', payload, folder, favoriteVideo)
      existingTaskIds.add(video.task_id)
    }
  }, [addPendingTask])

  useEffect(() => {
    if (!hydrated || !batchId) return

    let stopped = false
    let inFlight = false
    const refreshBatch = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const snapshot = await getBilibiliFavoriteBatch(batchId)
        if (!stopped) applyBatchSnapshot(snapshot)
      } catch (cause: unknown) {
        if (!stopped) {
          const failure = cause as BatchError
          setError(failure?.msg || failure?.message || '无法读取后端批次状态')
        }
      } finally {
        inFlight = false
      }
    }

    void refreshBatch()
    const timer = batchState === 'running' ? window.setInterval(refreshBatch, 3000) : undefined
    return () => {
      stopped = true
      if (timer !== undefined) window.clearInterval(timer)
    }
  }, [hydrated, batchId, batchState, applyBatchSnapshot])

  const submitBatch = async (
    items: FavoriteVideo[],
    config: GenerationConfig,
    favoriteFolder: FavoriteFolderInfo,
  ) => {
    setBatchSubmitting(true)
    setError('')
    try {
      const snapshot = await startBilibiliFavoriteBatch({
        favorite_folder: favoriteFolder,
        videos: items,
        config: {
          ...config,
          style: config.style || 'minimal',
          format: config.format || [],
          grid_size: config.grid_size || [],
        },
      })
      applyBatchSnapshot(snapshot)
    } catch (cause: unknown) {
      const failure = cause as BatchError
      setError(failure?.msg || failure?.message || '提交收藏夹批次失败')
    } finally {
      setBatchSubmitting(false)
    }
  }

  const startBatch = async () => {
    const items = videos.filter(video => selectedBvids.includes(getVideoKey(video)))
    if (hasMore) {
      setError('请先加载完整个收藏夹，再开始批量生成')
      return
    }
    if (items.length === 0) {
      setError('请至少选择一个视频')
      return
    }
    const config = getGenerationConfig()
    if (!config) return
    setNextIndex(0)
    await submitBatch(items, config, {
      id: favoriteId || favoriteUrl.trim(),
      title: favoriteTitle || 'Bilibili 收藏夹',
      url: favoriteUrl.trim(),
    })
  }

  const resumeBatch = async () => {
    if (!batchConfig) return
    const items = videos.filter(video => selectedBvids.includes(getVideoKey(video)))
    if (items.length === 0) {
      setError('没有可继续的已选视频')
      return
    }

    if (!batchId) {
      const remaining = items.slice(nextIndex).filter(video => video.status !== 'success' && video.status !== 'failed')
      if (remaining.length === 0) {
        setBatchState('done')
        return
      }
      const current = remaining[0]
      const resumedItems = current.status === 'running' && current.task_id
        ? [{ ...current, resume_task_id: current.task_id }, ...remaining.slice(1)]
        : remaining
      await submitBatch(resumedItems, batchConfig, {
        id: favoriteId || favoriteUrl.trim(),
        title: favoriteTitle || 'Bilibili 收藏夹',
        url: favoriteUrl.trim(),
      })
      return
    }

    setError('')
    try {
      applyBatchSnapshot(await resumeBilibiliFavoriteBatch(batchId))
    } catch (cause: unknown) {
      const failure = cause as BatchError
      setError(failure?.msg || failure?.message || '无法继续收藏夹批次')
    }
  }

  const retryFailed = async () => {
    const selectedVideos = videos.filter(video => selectedBvids.includes(getVideoKey(video)))
    const failedVideos = selectedVideos.filter(video => video.status === 'failed')
    if (failedVideos.length === 0 || !batchConfig) return
    await submitBatch(failedVideos, batchConfig, {
      id: favoriteId || favoriteUrl.trim(),
      title: favoriteTitle || 'Bilibili 收藏夹',
      url: favoriteUrl.trim(),
    })
  }

  const pauseBatch = async () => {
    if (batchState !== 'running' || pauseRequested || !batchId) return
    setPauseRequested(true)
    try {
      applyBatchSnapshot(await pauseBilibiliFavoriteBatch(batchId))
    } catch (cause: unknown) {
      const failure = cause as BatchError
      setPauseRequested(false)
      setError(failure?.msg || failure?.message || '无法暂停收藏夹批次')
    }
  }

  const clearBatch = () => {
    if (batchState === 'running') return
    if (batchId) void deleteBilibiliFavoriteBatch(batchId).catch(() => undefined)
    setVideos([])
    setSelectedBvids([])
    setFavoriteId('')
    setFavoriteTitle('')
    setPage(0)
    setTotal(0)
    setHasMore(false)
    setBatchConfig(null)
    setBatchId(null)
    setNextIndex(0)
    setBatchState('idle')
    setError('')
    localStorage.removeItem(STORAGE_KEY)
  }

  const toggleVideo = (videoKey: string) => {
    setSelectedBvids(current => current.includes(videoKey)
      ? current.filter(item => item !== videoKey)
      : [...current, videoKey])
  }

  const toggleAll = () => {
    setSelectedBvids(current => current.length === videos.length ? [] : videos.map(getVideoKey))
  }

  const finishedCount = videos.filter(video =>
    selectedBvids.includes(getVideoKey(video)) && (video.status === 'success' || video.status === 'failed')
  ).length
  const selectedCount = videos.filter(video => selectedBvids.includes(getVideoKey(video))).length

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={videos.length > 0
        ? 'flex h-[90vh] max-h-[48rem] min-h-0 max-w-3xl flex-col gap-4 overflow-hidden'
        : 'flex max-h-[90vh] max-w-3xl flex-col gap-4 overflow-hidden'}>
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <ListVideo className="h-5 w-5" />
            Bilibili 收藏夹批量生成
          </DialogTitle>
          <DialogDescription>
            使用设置中保存的 Bilibili Cookie 读取私有收藏夹；多 P 视频由后端按顺序执行，关闭浏览器不会中断批次，后端服务需保持运行。
          </DialogDescription>
        </DialogHeader>

        <div className="flex shrink-0 gap-2">
          <Input
            value={favoriteUrl}
            onChange={event => setFavoriteUrl(event.target.value)}
            placeholder="粘贴收藏夹链接，例如 bilibili.com/list/ml..."
            disabled={batchState === 'running'}
          />
          <Button type="button" onClick={previewFavorite} disabled={loading || batchSubmitting || batchState === 'running'}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ListVideo className="h-4 w-4" />}
            读取
          </Button>
        </div>

        {error && (
          <div className="flex max-h-24 shrink-0 items-start gap-2 overflow-y-auto rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {videos.length > 0 && (
          <>
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 text-sm">
              <div className="min-w-0">
                <span className="font-medium">{favoriteTitle}</span>
                <span className="ml-2 text-muted-foreground">
                  已载入 {videos.length} 个视频/分P · 收藏项 {total} · 已选 {selectedCount}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={toggleAll} disabled={batchConfig !== null || batchState === 'running' || batchSubmitting}>
                  {selectedCount === videos.length ? '取消全选' : '全选已载入'}
                </Button>
                {batchState !== 'running' && (
                  <Button type="button" variant="ghost" size="icon" title="清除批次" onClick={clearBatch}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>

            <ScrollArea className="min-h-0 flex-1 rounded border">
              <div className="divide-y">
                {videos.map(video => (
                  <label key={getVideoKey(video)} className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted/50">
                    <input
                      type="checkbox"
                      className="h-4 w-4 shrink-0 accent-primary"
                      checked={selectedBvids.includes(getVideoKey(video))}
                      disabled={batchConfig !== null || batchState === 'running' || batchSubmitting || video.status === 'success' || video.status === 'failed'}
                      onChange={() => toggleVideo(getVideoKey(video))}
                    />
                    {video.cover ? (
                      <img src={video.cover} alt="" loading="lazy" className="h-10 w-16 shrink-0 rounded object-cover" />
                    ) : (
                      <div className="h-10 w-16 shrink-0 rounded bg-muted" />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{video.title}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {[video.uploader, video.bvid].filter(Boolean).join(' · ')}
                      </span>
                    </span>
                    {video.status === 'running' && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                    {video.status === 'success' && <Check className="h-4 w-4 text-green-600" />}
                    {video.status === 'failed' && <span className="max-w-40 truncate text-xs text-red-600" title={video.error}>失败</span>}
                  </label>
                ))}
              </div>
            </ScrollArea>

            <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t bg-background pt-3">
              <div className="text-sm text-muted-foreground">
                {batchState === 'running'
                  ? pauseRequested
                    ? `当前视频完成后暂停 · ${finishedCount} / ${selectedCount}`
                    : `批量处理中 ${finishedCount} / ${selectedCount}，暂停会在当前视频完成后生效`
                  : batchState === 'done'
                    ? `批量完成：成功 ${videos.filter(video => video.status === 'success').length}，失败 ${videos.filter(video => video.status === 'failed').length}`
                    : batchState === 'paused'
                      ? `已暂停：完成 ${finishedCount} / ${selectedCount}`
                      : hasMore
                        ? '加载全部视频后才能开始，避免遗漏收藏夹内容'
                        : '后端逐个处理所选视频'}
              </div>
              <div className="flex gap-2">
                {hasMore && (
                  <Button type="button" variant="outline" onClick={loadAllPages} disabled={loadingAll || batchState === 'running' || batchSubmitting}>
                    {loadingAll && <Loader2 className="h-4 w-4 animate-spin" />}
                    {loadingAll ? `加载中 ${videos.length} / ${total}` : '加载全部'}
                  </Button>
                )}
                {batchState === 'running' ? (
                  <Button type="button" variant="outline" onClick={pauseBatch} disabled={pauseRequested || batchSubmitting}>
                    {pauseRequested
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <Pause className="h-4 w-4" />}
                    {pauseRequested ? '正在暂停…' : '暂停'}
                  </Button>
                ) : batchState === 'done' && videos.some(video => selectedBvids.includes(getVideoKey(video)) && video.status === 'failed') ? (
                  <Button type="button" variant="outline" onClick={retryFailed}>
                    重试失败项
                  </Button>
                ) : batchState === 'paused' ? (
                  <Button type="button" onClick={resumeBatch}>
                    <Play className="h-4 w-4" />继续
                  </Button>
                ) : (
                  <Button type="button" onClick={startBatch} disabled={selectedCount === 0 || hasMore || loadingAll || batchSubmitting}>
                    {batchSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    {batchSubmitting ? '提交中…' : '开始批量生成'}
                  </Button>
                )}
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default FavoriteBatchDialog
