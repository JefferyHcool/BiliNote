import React, { useEffect, useRef, useState } from 'react'
import { Markmap } from 'markmap-view'
import { transformer } from '@/lib/markmap.ts'
import { Toolbar, ToolbarButton } from 'markmap-toolbar'
import 'markmap-toolbar/dist/style.css'

export interface MarkmapEditorProps {
  /** 要渲染的 Markdown 文本 */
  value: string
  /** 内容变化时的回调 */
  onChange: (value: string) => void
  /** Toolbar 上要展示的 item id 列表，默认使用 Toolbar.defaultItems */
  toolbarItems?: string[]
  /** 自定义按钮列表，会依次注册 */
  customButtons?: ToolbarButton[]
  /** 容器 SVG 的高度，默认为 600px */
  height?: string
}

export default function MarkmapEditor({
  value,
  onChange,
  toolbarItems,
  customButtons = [],
  height = '600px',
}: MarkmapEditorProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const mmRef = useRef<Markmap>()
  const toolbarRef = useRef<HTMLDivElement>(null)

  // 用于跟踪是否处于全屏状态
  const [isFullscreen, setIsFullscreen] = useState(false)

  // 监听全屏状态变化
  useEffect(() => {
    const handler = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }
    document.addEventListener('fullscreenchange', handler)
    return () => {
      document.removeEventListener('fullscreenchange', handler)
    }
  }, [])

  // 进入全屏
  const enterFullscreen = () => {
    const el = svgRef.current?.parentElement
    if (el && el.requestFullscreen) {
      el.requestFullscreen()
    }
  }

  // 退出全屏
  const exitFullscreen = () => {
    if (document.exitFullscreen) {
      document.exitFullscreen()
    }
  }

  // 初始化 Markmap 实例 + Toolbar
  useEffect(() => {
    if (!svgRef.current || mmRef.current) return
    const mm = Markmap.create(svgRef.current)
    mmRef.current = mm

    if (toolbarRef.current) {
      toolbarRef.current.innerHTML = ''
      const toolbar = new Toolbar()
      toolbar.attach(mm)
      customButtons.forEach(btn => toolbar.register(btn))
      toolbar.setItems(toolbarItems ?? Toolbar.defaultItems)
      toolbarRef.current.appendChild(toolbar.render())
    }
  }, [customButtons, toolbarItems])

  // 当 value 变化时，重新渲染数据
  useEffect(() => {
    const mm = mmRef.current
    if (!mm) return
    const { root } = transformer.transform(value)
    mm.setData(root).then(() => mm.fit())
  }, [value])

  // 文本输入变化回调（如果你自行添加 textarea 编辑区）
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
  }

  return (
    <div className="relative flex h-full flex-col bg-white">
      {/* 全屏/退出全屏 按钮 */}
      <div className="absolute top-2 right-2 z-20 flex space-x-2">
        {isFullscreen ? (
          <button
            onClick={exitFullscreen}
            className="rounded p-1 hover:bg-gray-200"
            title="退出全屏"
          >
            🗗
          </button>
        ) : (
          <button onClick={enterFullscreen} className="rounded p-1 hover:bg-gray-200" title="全屏">
            🗖
          </button>
        )}
      </div>

      {/* 如果需要编辑区，就自己加一个 <textarea> 并把 handleChange 绑上 */}
      {/* <textarea value={value} onChange={handleChange} className="mb-2 p-2 border rounded" /> */}

      {/* 思维导图区 */}
      <svg ref={svgRef} className="w-full flex-1" style={{ height, overflow: 'auto' }} />

      {/* 如果你还想保留 markmap-toolbar */}
      {/* <div ref={toolbarRef} className="absolute right-2 bottom-2 z-10" /> */}
    </div>
  )
}
