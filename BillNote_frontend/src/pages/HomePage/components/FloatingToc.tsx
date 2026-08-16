import { ChevronDown, ChevronUp, EyeOff, ListTree } from 'lucide-react'
import { type RefObject, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface FloatingTocProps {
  contentRootRef: RefObject<HTMLDivElement | null>
  contentKey: string
  onExpandedChange?: (expanded: boolean) => void
}

interface TocHeading {
  id: string
  text: string
  level: number
}

type TocMode = 'expanded' | 'collapsed' | 'hidden'

const TOC_MODE_KEY = 'bilinote-floating-toc-mode'

const isDirectoryHeading = (text: string) => {
  const normalized = text
    .trim()
    .toLocaleLowerCase()
    .replace(/^[\d一二三四五六七八九十]+[.、．\s-]*/, '')
  return normalized === '目录'
    || normalized === '内容目录'
    || normalized === 'table of contents'
    || normalized === 'toc'
}

const getInitialMode = (): TocMode => {
  const saved = localStorage.getItem(TOC_MODE_KEY)
  return saved === 'collapsed' || saved === 'hidden' || saved === 'expanded'
    ? saved
    : 'expanded'
}

const FloatingToc = ({
  contentRootRef,
  contentKey,
  onExpandedChange,
}: FloatingTocProps) => {
  const [headings, setHeadings] = useState<TocHeading[]>([])
  const [activeId, setActiveId] = useState('')
  const [topDirectoryVisible, setTopDirectoryVisible] = useState(false)
  const [mode, setModeState] = useState<TocMode>(getInitialMode)

  const setMode = (nextMode: TocMode) => {
    setModeState(nextMode)
    localStorage.setItem(TOC_MODE_KEY, nextMode)
  }

  useEffect(() => {
    const contentRoot = contentRootRef.current
    if (!contentRoot) return
    const viewport = contentRoot
      .closest('[data-slot="scroll-area"]')
      ?.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')
    if (!viewport) return

    const allHeadingElements = Array.from(
      contentRoot.querySelectorAll<HTMLElement>('h1, h2, h3, h4'),
    )
    const directoryIndex = allHeadingElements.findIndex(element => (
      isDirectoryHeading(element.textContent || '')
    ))
    const outlineElements = allHeadingElements.filter(element => {
      const level = Number(element.tagName.slice(1))
      return level >= 2 && !isDirectoryHeading(element.textContent || '')
    })
    const fallbackElements = outlineElements.length > 0
      ? outlineElements
      : allHeadingElements.filter(element => !isDirectoryHeading(element.textContent || ''))

    const nextHeadings = fallbackElements
      .filter(element => element.id && element.textContent?.trim())
      .map(element => ({
        id: element.id,
        text: element.textContent!.trim(),
        level: Number(element.tagName.slice(1)),
      }))
    setHeadings(nextHeadings)

    let frame = 0
    const updatePosition = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        const viewportRect = viewport.getBoundingClientRect()
        const activeLine = viewportRect.top + 72
        let nextActive = fallbackElements[0]?.id || ''
        for (const heading of fallbackElements) {
          if (heading.getBoundingClientRect().top <= activeLine) nextActive = heading.id
          else break
        }
        setActiveId(nextActive)

        if (directoryIndex === -1) {
          setTopDirectoryVisible(false)
          return
        }
        const directoryHeading = allHeadingElements[directoryIndex]
        const nextHeading = allHeadingElements[directoryIndex + 1]
        const sectionTop = directoryHeading.getBoundingClientRect().top
        const sectionBottom = nextHeading
          ? nextHeading.getBoundingClientRect().top
          : directoryHeading.getBoundingClientRect().bottom + 160
        setTopDirectoryVisible(
          sectionBottom > viewportRect.top + 12
          && sectionTop < viewportRect.bottom - 12,
        )
      })
    }

    updatePosition()
    viewport.addEventListener('scroll', updatePosition, { passive: true })
    const resizeObserver = new ResizeObserver(updatePosition)
    resizeObserver.observe(viewport)
    resizeObserver.observe(contentRoot)
    return () => {
      window.cancelAnimationFrame(frame)
      viewport.removeEventListener('scroll', updatePosition)
      resizeObserver.disconnect()
    }
  }, [contentKey, contentRootRef])

  const expandedAndVisible = headings.length > 0
    && !topDirectoryVisible
    && mode === 'expanded'

  useEffect(() => {
    onExpandedChange?.(expandedAndVisible)
    return () => onExpandedChange?.(false)
  }, [expandedAndVisible, onExpandedChange])

  if (headings.length === 0 || topDirectoryVisible) return null

  const scrollToHeading = (headingId: string) => {
    const heading = Array.from(
      contentRootRef.current?.querySelectorAll<HTMLElement>('h1, h2, h3, h4') || [],
    ).find(element => element.id === headingId)
    heading?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const minimumLevel = Math.min(...headings.map(heading => heading.level))

  if (mode === 'hidden') {
    return (
      <Button
        type="button"
        variant="outline"
        size="icon"
        title="显示悬浮目录"
        className="absolute top-2 right-3 z-20 h-8 w-8 rounded-full bg-white/90 shadow-sm backdrop-blur"
        onClick={() => setMode('collapsed')}
      >
        <ListTree className="h-4 w-4" />
      </Button>
    )
  }

  if (mode === 'collapsed') {
    return (
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="absolute top-2 right-3 z-20 h-8 bg-white/90 text-xs shadow-sm backdrop-blur"
        onClick={() => setMode('expanded')}
      >
        <ListTree className="h-3.5 w-3.5" />
        目录
        <ChevronDown className="h-3.5 w-3.5" />
      </Button>
    )
  }

  return (
    <aside
      data-slot="floating-toc"
      className="absolute top-2 right-3 z-20 w-48 overflow-hidden rounded-lg border bg-white/95 text-xs shadow-md backdrop-blur xl:w-56"
    >
      <div className="flex h-8 items-center border-b px-2">
        <ListTree className="mr-1.5 h-3.5 w-3.5 text-blue-600" />
        <span className="font-medium">目录</span>
        <div className="ml-auto flex items-center">
          <button
            type="button"
            title="折叠目录"
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
            onClick={() => setMode('collapsed')}
          >
            <ChevronUp className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            title="隐藏目录"
            className="rounded p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
            onClick={() => setMode('hidden')}
          >
            <EyeOff className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <nav className="max-h-[46vh] overflow-y-auto py-1.5">
        {headings.map(heading => (
          <button
            key={heading.id}
            type="button"
            title={heading.text}
            className={cn(
              'block w-full truncate border-l-2 py-1 pr-2 text-left transition-colors',
              activeId === heading.id
                ? 'border-blue-500 bg-blue-50 font-medium text-blue-700'
                : 'border-transparent text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900',
            )}
            style={{ paddingLeft: `${8 + Math.min(heading.level - minimumLevel, 2) * 10}px` }}
            onClick={() => scrollToHeading(heading.id)}
          >
            {heading.text}
          </button>
        ))}
      </nav>
    </aside>
  )
}

export default FloatingToc
