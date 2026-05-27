'use client'

import { useEffect, useState } from 'react'
import { Copy, Download, BrainCircuit, MessageSquare, Captions } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { videoPlatforms } from '@/constant/note'

interface VersionNote {
  ver_id: string
  model_name?: string
  style?: string
  created_at?: string
}

interface NoteHeaderProps {
  currentTask?: {
    markdown: VersionNote[] | string
  } | null
  platform?: string
  isMultiVersion: boolean
  currentVerId: string
  setCurrentVerId: (id: string) => void
  modelName: string
  style: string
  noteStyles: { value: string; label: string }[]
  onCopy: () => void
  onDownload: () => void
  createAt?: string | Date
  showTranscribe: boolean
  setShowTranscribe: (show: boolean) => void
  showChat?: false | 'half' | 'full'
  setShowChat?: (mode: false | 'half' | 'full') => void
  viewMode: 'map' | 'preview'
  setViewMode: (mode: 'map' | 'preview') => void
}

export function MarkdownHeader({
  currentTask,
  platform,
  isMultiVersion,
  currentVerId,
  setCurrentVerId,
  modelName,
  style,
  noteStyles,
  onCopy,
  onDownload,
  createAt,
  showTranscribe,
  setShowTranscribe,
  showChat,
  setShowChat,
  viewMode,
  setViewMode,
}: NoteHeaderProps) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let timer: NodeJS.Timeout
    if (copied) {
      timer = setTimeout(() => setCopied(false), 2000)
    }
    return () => clearTimeout(timer)
  }, [copied])

  const handleCopy = () => {
    onCopy()
    setCopied(true)
  }

  const styleName = noteStyles.find(v => v.value === style)?.label || style
  const versions: VersionNote[] = Array.isArray(currentTask?.markdown) ? currentTask.markdown : []
  const platformMeta = videoPlatforms.find(item => item.value === platform)
  const platformName = platformMeta?.label || platform || ''
  const PlatformLogo = platformMeta?.logo

  const formatDate = (date: string | Date | undefined) => {
    if (!date) return ''
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return ''
    return d
      .toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
      .replace(/\//g, '-')
  }

  return (
    <div className="sticky top-0 z-10 flex min-h-12 flex-col gap-2 border-b bg-white/95 px-3 py-2 backdrop-blur-sm sm:px-4">
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto">
        {isMultiVersion && (
          <Select value={currentVerId} onValueChange={setCurrentVerId}>
            <SelectTrigger className="h-8 w-[132px] shrink-0 text-sm sm:w-[160px]">
              <div className="flex min-w-0 items-center truncate">
                {(() => {
                  const idx = versions.findIndex(v => v.ver_id === currentVerId)
                  return idx !== -1 ? `版本（${currentVerId.slice(-6)}）` : ''
                })()}
              </div>
            </SelectTrigger>

            <SelectContent>
              {versions.map(v => {
                const shortId = v.ver_id.slice(-6)
                return (
                  <SelectItem key={v.ver_id} value={v.ver_id}>
                    {`版本（${shortId}）`}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        )}

        {platformName && (
          <Badge
            variant="secondary"
            className="max-w-[8rem] shrink-0 gap-1.5 truncate bg-white text-neutral-700 ring-1 ring-neutral-200 hover:bg-neutral-50"
            title={platformName}
          >
            {PlatformLogo && (
              <span className="flex h-4 w-4 shrink-0 items-center justify-center overflow-hidden rounded-sm">
                <PlatformLogo />
              </span>
            )}
            {platformName}
          </Badge>
        )}

        {modelName && (
          <Badge
            variant="secondary"
            className="max-w-[9rem] shrink-0 truncate bg-pink-100 text-pink-700 hover:bg-pink-200"
            title={modelName}
          >
            {modelName}
          </Badge>
        )}
        {styleName && (
          <Badge
            variant="secondary"
            className="max-w-[8rem] shrink-0 truncate bg-cyan-100 text-cyan-700 hover:bg-cyan-200"
            title={styleName}
          >
            {styleName}
          </Badge>
        )}
      </div>

      <div className="flex w-full min-w-0 shrink-0 items-center justify-between gap-3">
        <div className="text-muted-foreground shrink-0 text-sm whitespace-nowrap">
          {createAt ? `创建时间: ${formatDate(createAt)}` : ''}
        </div>

        <div className="flex min-w-0 items-center justify-end gap-1 overflow-x-auto">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  onClick={() => {
                    setViewMode(viewMode === 'preview' ? 'map' : 'preview')
                  }}
                  variant="ghost"
                  size="sm"
                  className="h-8 min-w-8 px-2 sm:min-w-24"
                >
                  <BrainCircuit className="h-4 w-4" />
                  <span className="hidden text-sm sm:inline">
                    {viewMode === 'preview' ? '思维导图' : '返回笔记'}
                  </span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>切换视图</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  onClick={() => {
                    setShowTranscribe(!showTranscribe)
                  }}
                  variant={showTranscribe ? 'default' : 'ghost'}
                  size="sm"
                  className="h-8 px-2"
                >
                  <Captions className="h-4 w-4" />
                  <span className="hidden text-sm sm:inline">原文参照</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>原文参照</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {setShowChat && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    onClick={() => setShowChat(showChat ? false : 'half')}
                    variant={showChat ? 'default' : 'ghost'}
                    size="sm"
                    className="h-8 px-2"
                  >
                    <MessageSquare className="h-4 w-4" />
                    <span className="hidden text-sm sm:inline">AI 问答</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>基于笔记内容的 AI 问答</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button onClick={handleCopy} variant="ghost" size="sm" className="h-8 px-2">
                  <Copy className="h-4 w-4" />
                  <span className="hidden text-sm sm:inline">{copied ? '已复制' : '复制'}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>复制内容</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button onClick={onDownload} variant="ghost" size="sm" className="h-8 px-2">
                  <Download className="h-4 w-4" />
                  <span className="hidden text-sm sm:inline">导出Md</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>下载为 Markdown 文件</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    </div>
  )
}
