import { useEffect, useRef, useState } from 'react'
import { Markmap } from 'markmap-view'
import { transformer } from '@/lib/markmap.ts'
import { Toolbar } from 'markmap-toolbar'
import 'markmap-toolbar/dist/style.css'
import JSZip from 'jszip'

interface MarkmapNode {
  content?: string
  payload?: { content?: string }
  children?: MarkmapNode[]
}

export interface MarkmapEditorProps {
  /** 要渲染的 Markdown 文本 */
  value: string
  /** 内容变化时的回调 */
  onChange: (value: string) => void
  /** Toolbar 上要展示的 item id 列表，默认使用 Toolbar.defaultItems */
  toolbarItems?: string[]
  /** 自定义按钮列表，会依次注册 */
  customButtons?: unknown[]
  /** 容器 SVG 的高度，默认为 600px */
  height?: string
  /** 文档标题，用于导出HTML时的文件名 */
  title?: string
}

export default function MarkmapEditor({
  value,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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
      const { root } = transformer.transform(value)
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
      const { root } = transformer.transform(value);

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
        const text = decodeHtmlEntities(html);
        // 移除HTML标签
        const div = document.createElement('div');
        div.innerHTML = text;
        return div.textContent || div.innerText || text;
      };

      interface XMindNode {
        id: string
        class: string
        title: string
        children?: { attached: XMindNode[] }
      }

      // 将 markmap 节点转换为 XMind 节点格式
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const convertToXMindNode = (node: MarkmapNode, isRoot = false): XMindNode => {
        const rawTitle = node.content || node.payload?.content || '未命名';
        const xmindNode: XMindNode = {
          id: generateId(),
          class: 'topic',
          title: stripHtml(rawTitle),
        };

        if (node.children && node.children.length > 0) {
          xmindNode.children = {
            attached: node.children.map((child) => convertToXMindNode(child, false))
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

      const svgEl = svgRef.current;
      const mm = mmRef.current;

      // 先调用fit()确保显示完整的思维导图内容
      await mm.fit();
      // 等待渲染完成
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // 获取SVG实际尺寸
      const svgWidth = svgEl.width.baseVal.value || svgEl.clientWidth || 800;
      const svgHeight = svgEl.height.baseVal.value || svgEl.clientHeight || 600;
      
      // 设置足够大的缩放比例以确保高清输出
      const scale = 3;
      
      // 克隆SVG以避免修改原始SVG
      const clonedSvg = svgEl.cloneNode(true) as SVGSVGElement;
      
      // 设置SVG的背景为白色
      const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
      style.textContent = 'svg { background-color: white; }';
      clonedSvg.insertBefore(style, clonedSvg.firstChild);
      
      // 确保SVG有正确的命名空间
      clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clonedSvg.setAttribute('width', svgWidth.toString());
      clonedSvg.setAttribute('height', svgHeight.toString());
      
      // 将SVG转换为Data URI (避免使用Blob URL来解决跨域问题)
      const svgData = new XMLSerializer().serializeToString(clonedSvg);
      const svgBase64 = btoa(unescape(encodeURIComponent(svgData)));
      const dataUri = `data:image/svg+xml;base64,${svgBase64}`;
      
      // 创建Canvas
      const canvas = document.createElement('canvas');
      canvas.width = svgWidth * scale;
      canvas.height = svgHeight * scale;
      
      // 获取上下文并设置白色背景
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        throw new Error('无法获取Canvas上下文');
      }
      
      // 设置白色背景
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // 创建Image对象
      const img = new Image();
      
      // 当图片加载完成后，在Canvas上绘制并导出
      img.onload = () => {
        try {
          // 应用缩放
          ctx.setTransform(scale, 0, 0, scale, 0, 0);
          
          // 绘制SVG
          ctx.drawImage(img, 0, 0);
          
          // 重置变换
          ctx.setTransform(1, 0, 0, 1, 0, 0);
          
          // 将Canvas转换为PNG Blob
          canvas.toBlob((blob) => {
            if (blob) {
              // 创建下载链接
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `${title || 'mindmap'}.png`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            } else {
              console.error('无法创建Blob对象');
            }
          }, 'image/png');
        } catch (err) {
          console.error('Canvas处理失败:', err);
        }
      };
      
      // 设置图片加载错误处理
      img.onerror = (error) => {
        console.error('导出PNG失败（图片加载错误）:', error);
      };
      
      // 开始加载SVG图像 (使用Data URI而不是Blob URL)
      img.src = dataUri;
      
    } catch (error) {
      console.error('导出PNG失败:', error);
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
    const { root } = transformer.transform(value)
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
        >
          🖼️
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

      {/* 如果需要编辑区，就自己加一个 <textarea> 并把 handleChange 绑上 */}
      {/* <textarea value={value} onChange={handleChange} className="mb-2 p-2 border rounded" /> */}

      {/* 思维导图区 */}
      <svg ref={svgRef} className="w-full flex-1" style={{ height, overflow: 'auto' }} />

      {/* 如果你还想保留 markmap-toolbar */}
      {/* <div ref={toolbarRef} className="absolute right-2 bottom-2 z-10" /> */}
    </div>
  )
}
