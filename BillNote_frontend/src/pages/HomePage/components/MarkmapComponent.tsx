import { useEffect, useRef, useState } from 'react'
import { Markmap } from 'markmap-view'
import { transformer } from '@/lib/markmap.ts'
import { Toolbar } from 'markmap-toolbar'
import 'markmap-toolbar/dist/style.css'
import JSZip from 'jszip'

const MIN_EXPORT_FONT_PX = 256
const MIN_EXPORT_WIDTH = 12800
const WEB_EXPORT_SCALE_FACTOR = 0.34
const MAX_EXPORT_SCALE = 24
const MAX_CANVAS_SIDE = 32767
const MAX_CANVAS_PIXELS = 268000000

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
      } else {
        reject(new Error('无法创建PNG图片'))
      }
    }, 'image/png')
  })
}

function createSvgElement<K extends keyof SVGElementTagNameMap>(tag: K): SVGElementTagNameMap[K] {
  return document.createElementNS('http://www.w3.org/2000/svg', tag)
}

function sanitizeSvgForCanvas(svg: SVGSVGElement): SVGSVGElement {
  const cloned = svg.cloneNode(true) as SVGSVGElement

  // markmap 会在 SVG 的顶层 <g> 上写入当前预览视口的 pan/zoom transform。
  // 导出时我们按内容 bbox 裁剪，如果保留这个视口 transform，会产生双重偏移，
  // 导致图片内容跑到角落并留下大片空白。这里只移除顶层视口 transform，
  // 保留内部节点自身的布局 transform。
  cloned.querySelector(':scope > g')?.removeAttribute('transform')

  cloned.querySelectorAll('image').forEach(el => el.remove())
  cloned.querySelectorAll('foreignObject').forEach((foreignObject) => {
    const textContent = foreignObject.textContent?.replace(/\s+/g, ' ').trim()
    if (!textContent) {
      foreignObject.remove()
      return
    }

    const x = Number(foreignObject.getAttribute('x') || 0)
    const y = Number(foreignObject.getAttribute('y') || 0)
    const height = Number(foreignObject.getAttribute('height') || 20)
    const text = createSvgElement('text')
    text.setAttribute('x', String(x))
    text.setAttribute('y', String(y + height / 2))
    text.setAttribute('dominant-baseline', 'middle')
    text.setAttribute('font-size', '14')
    text.setAttribute('font-family', 'Arial, "Microsoft YaHei", sans-serif')
    text.setAttribute('fill', '#333')
    text.textContent = textContent
    foreignObject.replaceWith(text)
  })

  return cloned
}

function getExportFontSize(svg: SVGSVGElement): number {
  const text = svg.querySelector('text, foreignObject')
  if (!text) return 14

  const fontSize = Number.parseFloat(getComputedStyle(text).fontSize || '')
  if (Number.isFinite(fontSize) && fontSize > 0) return fontSize

  const attrSize = Number.parseFloat(text.getAttribute('font-size') || '')
  return Number.isFinite(attrSize) && attrSize > 0 ? attrSize : 14
}

function getMindmapBounds(svg: SVGSVGElement) {
  const target = svg.querySelector('g') || svg
  const bbox = target.getBBox()
  const padding = 50
  return {
    x: Math.floor(bbox.x - padding),
    y: Math.floor(bbox.y - padding),
    width: Math.max(Math.ceil(bbox.width + padding * 2), 1),
    height: Math.max(Math.ceil(bbox.height + padding * 2), 1),
  }
}

function stripMindmapImages(markdown: string) {
  return (markdown || '')
    // 思维导图只保留文字结构，图片节点会让预览排版和 PNG 导出效果都很差。
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/<img\b[^>]*>/gi, '')
}

function transformMindmap(markdown: string) {
  return transformer.transform(stripMindmapImages(markdown))
}

function createExportSvg(svgEl: SVGSVGElement) {
  const bounds = getMindmapBounds(svgEl)
  const clonedSvg = sanitizeSvgForCanvas(svgEl)

  clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink')
  clonedSvg.setAttribute('width', String(bounds.width))
  clonedSvg.setAttribute('height', String(bounds.height))
  clonedSvg.setAttribute('viewBox', `${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`)
  clonedSvg.setAttribute('preserveAspectRatio', 'xMidYMid meet')

  const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  bgRect.setAttribute('x', String(bounds.x))
  bgRect.setAttribute('y', String(bounds.y))
  bgRect.setAttribute('width', String(bounds.width))
  bgRect.setAttribute('height', String(bounds.height))
  bgRect.setAttribute('fill', 'white')
  const firstG = clonedSvg.querySelector('g')
  clonedSvg.insertBefore(bgRect, firstG || clonedSvg.firstChild)

  return { clonedSvg, ...bounds }
}

async function exportSvgToPngBlob(svgEl: SVGSVGElement): Promise<Blob> {
  const { clonedSvg, width, height } = createExportSvg(svgEl)
  const svgData = new XMLSerializer().serializeToString(clonedSvg)
  const svgUrl = URL.createObjectURL(new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' }))

  try {
    const img = new Image()
    img.decoding = 'async'
    img.src = svgUrl
    await img.decode()

    // 按导图内容尺寸和字号动态反推 PNG 倍率，而不是按预览容器或固定倍率导出。
    const fontScale = MIN_EXPORT_FONT_PX / getExportFontSize(svgEl)
    const widthScale = MIN_EXPORT_WIDTH / width
    const rawScale = Math.max(window.devicePixelRatio || 1, fontScale, widthScale)
    const sideLimitScale = Math.min(MAX_CANVAS_SIDE / width, MAX_CANVAS_SIDE / height)
    const pixelLimitScale = Math.sqrt(MAX_CANVAS_PIXELS / (width * height))
    const baseScale = Math.min(rawScale, MAX_EXPORT_SCALE, sideLimitScale, pixelLimitScale)
    const scale = Math.max(1, baseScale * WEB_EXPORT_SCALE_FACTOR)

    let currentScale = scale
    let lastError: unknown
    while (currentScale >= 1) {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = Math.ceil(width * currentScale)
        canvas.height = Math.ceil(height * currentScale)

        const ctx = canvas.getContext('2d')
        if (!ctx) {
          throw new Error('无法获取Canvas上下文')
        }

        ctx.fillStyle = '#FFFFFF'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.setTransform(currentScale, 0, 0, currentScale, 0, 0)
        ctx.drawImage(img, 0, 0, width, height)
        ctx.setTransform(1, 0, 0, 1, 0, 0)

        return await canvasToBlob(canvas)
      } catch (error) {
        lastError = error
        currentScale = Math.floor(currentScale / 2)
      }
    }
    throw lastError || new Error('导出PNG失败')
  } finally {
    URL.revokeObjectURL(svgUrl)
  }
}

export interface MarkmapEditorProps {
  /** 要渲染的 Markdown 文本 */
  value: string
  /** 内容变化时的回调 */
  onChange: (value: string) => void
  /** Toolbar 上要展示的 item id 列表，默认使用 Toolbar.defaultItems */
  toolbarItems?: string[]
  /** 自定义按钮列表，会依次注册 */
  customButtons?: any[]
  /** 容器 SVG 的高度，默认为 600px */
  height?: string
  /** 文档标题，用于导出HTML时的文件名 */
  title?: string
}

export default function MarkmapEditor({
  value,
  onChange,
  toolbarItems,
  customButtons = [],
  height = '600px',
  title = 'mindmap',
}: MarkmapEditorProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const mmRef = useRef<Markmap | undefined>()
  const toolbarRef = useRef<HTMLDivElement>(null)

  // 用于跟踪是否处于全屏状态
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [pngAction, setPngAction] = useState<'idle' | 'exporting' | 'copying'>('idle')
  const [pngMessage, setPngMessage] = useState('')

  const showPngMessage = (message: string) => {
    setPngMessage(message)
    window.setTimeout(() => setPngMessage(''), 2500)
  }

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
  
  // 导出HTML思维导图
  const exportHtml = () => {
    try {
      const { root } = transformMindmap(value)
      const data = JSON.stringify(root)
      
      // 创建HTML内容
      const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title || 'BiliNote思维导图'}</title>
  <style>
  body {
    margin: 0;
    padding: 0;
    font-family: sans-serif;
  }
  #mindmap {
    display: block;
    width: 100%;
    height: 100vh;
  }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <script src="https://cdn.jsdelivr.net/npm/markmap-view@0.18.10"></script>
</head>
<body>
  <svg id="mindmap"></svg>
  <script>
  (async () => {
    const { markmap } = window;
    const { Markmap } = markmap;
    const mm = Markmap.create(document.getElementById('mindmap'));
    mm.setData(${data});
    mm.fit();
  })();
  </script>
</body>
</html>`;
      
      const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title || 'mindmap'}.html`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('导出HTML失败:', error);
    }
  };

  // 导出SVG思维导图（矢量图）
  const exportSvg = async () => {
    try {
      if (!svgRef.current || !mmRef.current) return;

      const svgEl = svgRef.current;
      const mm = mmRef.current;

      // 先调用fit()确保显示完整的思维导图内容
      await mm.fit();
      // 等待渲染完成
      await new Promise(resolve => setTimeout(resolve, 100));

      // 克隆SVG以避免修改原始SVG
      const clonedSvg = svgEl.cloneNode(true) as SVGSVGElement;

      // 获取SVG内容的实际边界框
      const gElement = svgEl.querySelector('g');
      if (gElement) {
        const bbox = gElement.getBBox();
        // 添加一些边距
        const padding = 50;
        const viewBoxX = bbox.x - padding;
        const viewBoxY = bbox.y - padding;
        const viewBoxWidth = bbox.width + padding * 2;
        const viewBoxHeight = bbox.height + padding * 2;

        // 设置viewBox以确保SVG可以无限缩放
        clonedSvg.setAttribute('viewBox', `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`);
        // 移除固定尺寸，让SVG根据viewBox自适应
        clonedSvg.removeAttribute('width');
        clonedSvg.removeAttribute('height');
        // 设置默认尺寸为100%，可以在任何容器中自适应
        clonedSvg.setAttribute('width', '100%');
        clonedSvg.setAttribute('height', '100%');
        // 保持宽高比
        clonedSvg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      }

      // 设置SVG的背景为白色
      const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
      style.textContent = 'svg { background-color: white; }';
      clonedSvg.insertBefore(style, clonedSvg.firstChild);

      // 添加白色背景矩形（确保背景在所有查看器中都是白色）
      const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      const viewBox = clonedSvg.getAttribute('viewBox')?.split(' ').map(Number) || [0, 0, 800, 600];
      bgRect.setAttribute('x', viewBox[0].toString());
      bgRect.setAttribute('y', viewBox[1].toString());
      bgRect.setAttribute('width', viewBox[2].toString());
      bgRect.setAttribute('height', viewBox[3].toString());
      bgRect.setAttribute('fill', 'white');
      // 插入到最前面作为背景
      const firstG = clonedSvg.querySelector('g');
      if (firstG) {
        clonedSvg.insertBefore(bgRect, firstG);
      } else {
        clonedSvg.insertBefore(bgRect, clonedSvg.firstChild);
      }

      // 确保SVG有正确的命名空间
      clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clonedSvg.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

      // 序列化SVG
      const svgData = new XMLSerializer().serializeToString(clonedSvg);

      // 创建下载
      const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title || 'mindmap'}.svg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('导出SVG失败:', error);
    }
  };

  // 导出XMind格式思维导图
  const exportXMind = async () => {
    try {
      const { root } = transformMindmap(value);

      // 生成唯一ID
      const generateId = () => Math.random().toString(36).substring(2, 15);

      // 解码HTML实体（如 &#x5b9e; -> 实，&#12345; -> 对应字符）
      const decodeHtmlEntities = (text: string): string => {
        if (!text) return text;

        // 首先手动处理十六进制数字实体 &#xHHHH;
        let decoded = text.replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => {
          return String.fromCodePoint(parseInt(hex, 16));
        });

        // 处理十进制数字实体 &#DDDD;
        decoded = decoded.replace(/&#(\d+);/g, (_, dec) => {
          return String.fromCodePoint(parseInt(dec, 10));
        });

        // 使用textarea处理命名实体（如 &amp; &lt; &gt; 等）
        const textarea = document.createElement('textarea');
        textarea.innerHTML = decoded;
        return textarea.value;
      };

      // 清理HTML标签，只保留纯文本
      const stripHtml = (html: string): string => {
        if (!html) return html;
        // 先解码HTML实体
        let text = decodeHtmlEntities(html);
        // 移除HTML标签
        const div = document.createElement('div');
        div.innerHTML = text;
        return div.textContent || div.innerText || text;
      };

      // 将 markmap 节点转换为 XMind 节点格式
      const convertToXMindNode = (node: any, isRoot = false): any => {
        const rawTitle = node.content || node.payload?.content || '未命名';
        const xmindNode: any = {
          id: generateId(),
          class: isRoot ? 'topic' : 'topic',
          title: stripHtml(rawTitle),
        };

        if (node.children && node.children.length > 0) {
          xmindNode.children = {
            attached: node.children.map((child: any) => convertToXMindNode(child, false))
          };
        }

        return xmindNode;
      };

      const rootTopic = convertToXMindNode(root, true);
      const sheetId = generateId();

      // XMind content.json 结构
      const content = [{
        id: sheetId,
        class: 'sheet',
        title: stripHtml(title) || '思维导图',
        rootTopic: rootTopic,
        topicPositioning: 'fixed'
      }];

      // XMind metadata.json
      const metadata = {
        creator: {
          name: 'BiliNote',
          version: '1.0.0'
        }
      };

      // XMind manifest.json
      const manifest = {
        'file-entries': {
          'content.json': {},
          'metadata.json': {}
        }
      };

      // 使用 JSZip 创建 .xmind 文件
      // 直接传入字符串，JSZip会自动处理UTF-8编码
      const zip = new JSZip();
      zip.file('content.json', JSON.stringify(content, null, 2));
      zip.file('metadata.json', JSON.stringify(metadata, null, 2));
      zip.file('manifest.json', JSON.stringify(manifest, null, 2));

      // 生成 ZIP 并下载
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title || 'mindmap'}.xmind`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('导出XMind失败:', error);
    }
  };

  // 导出PNG思维导图
  const exportPng = async () => {
    try {
      if (!svgRef.current || !mmRef.current) return;

      setPngAction('exporting');
      setPngMessage('正在生成高清 PNG…');
      const blob = await exportSvgToPngBlob(svgRef.current);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title || 'mindmap'}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showPngMessage('PNG 已开始下载');
    } catch (error) {
      console.error('导出PNG失败:', error);
      showPngMessage('导出 PNG 失败，请查看控制台');
    } finally {
      setPngAction('idle');
    }
  };

  // 复制PNG思维导图
  const copyPng = async () => {
    try {
      if (!svgRef.current || !mmRef.current) return;

      setPngAction('copying');
      setPngMessage('正在复制高清 PNG…');
      await navigator.clipboard.write([
        new ClipboardItem({
          'image/png': exportSvgToPngBlob(svgRef.current),
        }),
      ]);
      showPngMessage('PNG 已复制');
    } catch (error) {
      console.error('复制PNG失败:', error);
      showPngMessage('复制 PNG 失败，请查看控制台');
    } finally {
      setPngAction('idle');
    }
  };

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
    const { root } = transformMindmap(value)
    mm.setData(root).then(() => mm.fit())
  }, [value])

  // 文本输入变化回调（如果你自行添加 textarea 编辑区）
  // const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  //   onChange(e.target.value)
  // }

  return (
    <div className="relative flex h-full flex-col bg-white">
      {/* 全屏/退出全屏 按钮 */}
      <div className="absolute top-2 right-2 z-20 flex space-x-2">
        <button
          onClick={exportXMind}
          className="rounded p-1 hover:bg-gray-200"
          title="导出XMind格式"
        >
          🧠
        </button>
        <button
          onClick={exportSvg}
          className="rounded p-1 hover:bg-gray-200"
          title="导出SVG矢量图（可无限放大）"
        >
          📐
        </button>
        <button
          onClick={exportPng}
          className="rounded p-1 hover:bg-gray-200"
          title="导出PNG图片"
          disabled={pngAction !== 'idle'}
        >
          {pngAction === 'exporting' ? '⏳' : '🖼️'}
        </button>
        <button
          onClick={copyPng}
          className="rounded p-1 hover:bg-gray-200"
          title="复制PNG图片"
          disabled={pngAction !== 'idle'}
        >
          {pngAction === 'copying' ? '⏳' : '📋'}
        </button>
        <button
          onClick={exportHtml}
          className="rounded p-1 hover:bg-gray-200"
          title="导出HTML（可交互）"
        >
          💾
        </button>
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
      {pngMessage && (
        <div className="absolute top-11 right-2 z-20 rounded bg-white/95 px-2 py-1 text-xs text-gray-600 shadow">
          {pngMessage}
        </div>
      )}

      {/* 如果需要编辑区，就自己加一个 <textarea> 并把 handleChange 绑上 */}
      {/* <textarea value={value} onChange={handleChange} className="mb-2 p-2 border rounded" /> */}

      {/* 思维导图区 */}
      <svg ref={svgRef} className="w-full flex-1" style={{ height, overflow: 'auto' }} />

      {/* 如果你还想保留 markmap-toolbar */}
      {/* <div ref={toolbarRef} className="absolute right-2 bottom-2 z-10" /> */}
    </div>
  )
}
