<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { absolutizeMarkdownImages, stripSourceLink } from '~/logic/api'

const props = defineProps<{ markdown: string }>()

const wrapRef = ref<HTMLDivElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
let mm: Markmap | null = null
let resizeObserver: ResizeObserver | null = null
const transformer = new Transformer()
const MIN_EXPORT_FONT_PX = 256
const MIN_EXPORT_WIDTH = 12800
const MAX_EXPORT_SCALE = 24
const MAX_CANVAS_SIDE = 32767

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob)
        resolve(blob)
      else
        reject(new Error('导出思维导图图片失败'))
    }, 'image/png')
  })
}

function createSvgElement<K extends keyof SVGElementTagNameMap>(tag: K): SVGElementTagNameMap[K] {
  return document.createElementNS('http://www.w3.org/2000/svg', tag)
}

function sanitizeSvgForCanvas(svg: SVGSVGElement): SVGSVGElement {
  const cloned = svg.cloneNode(true) as SVGSVGElement

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
  if (!text)
    return 14

  const fontSize = Number.parseFloat(getComputedStyle(text).fontSize || '')
  if (Number.isFinite(fontSize) && fontSize > 0)
    return fontSize

  const attrSize = Number.parseFloat(text.getAttribute('font-size') || '')
  return Number.isFinite(attrSize) && attrSize > 0 ? attrSize : 14
}

function stripMindmapNoise(md: string): string {
  return absolutizeMarkdownImages(stripSourceLink(md || ''))
    // 笔记里的截图/封面图片在思维导图中会被当作超大 SVG foreignObject，
    // 容易把导图挤成截图里那种“只剩半框/一条竖线”的效果。导图只保留文字层级。
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/<img\b[^>]*>/gi, '')
}

async function fit() {
  await nextTick()
  requestAnimationFrame(() => mm?.fit())
}

async function render() {
  if (!svgRef.value)
    return
  const { root } = transformer.transform(stripMindmapNoise(props.markdown))
  if (!mm)
    mm = Markmap.create(svgRef.value, { autoFit: true }, root)
  else
    await mm.setData(root)
  await fit()
}

async function toPngBlob(): Promise<Blob> {
  await fit()
  await nextTick()
  if (!svgRef.value)
    throw new Error('思维导图尚未渲染完成')

  const svg = svgRef.value
  const bbox = svg.getBBox()
  const padding = 48
  const x = Math.floor(bbox.x - padding)
  const y = Math.floor(bbox.y - padding)
  const width = Math.max(Math.ceil(bbox.width + padding * 2), 1)
  const height = Math.max(Math.ceil(bbox.height + padding * 2), 1)
  const cloned = sanitizeSvgForCanvas(svg)

  cloned.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  cloned.setAttribute('width', String(width))
  cloned.setAttribute('height', String(height))
  cloned.setAttribute('viewBox', `${x} ${y} ${width} ${height}`)
  cloned.insertAdjacentHTML('afterbegin', `<rect width="100%" height="100%" fill="#fff"/>`)

  const svgText = new XMLSerializer().serializeToString(cloned)
  const url = URL.createObjectURL(new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' }))

  try {
    const img = new Image()
    img.decoding = 'async'
    img.src = url
    await img.decode()

    // 不写死某个导出宽度：按导图内容和文字字号动态反推 PNG 倍率。
    // 目标是让导出的正文至少有 MIN_EXPORT_FONT_PX 像素高，小图自动放大，
    // 大图则按内容尺寸导出；同时限制最大边长，避免复杂导图撑爆内存。
    const fontScale = MIN_EXPORT_FONT_PX / getExportFontSize(svg)
    const widthScale = MIN_EXPORT_WIDTH / width
    const rawScale = Math.max(window.devicePixelRatio || 1, fontScale, widthScale)
    const sideLimitScale = Math.min(MAX_CANVAS_SIDE / width, MAX_CANVAS_SIDE / height)
    const scale = Math.max(1, Math.min(rawScale, MAX_EXPORT_SCALE, sideLimitScale))
    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(width * scale)
    canvas.height = Math.ceil(height * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx)
      throw new Error('当前浏览器不支持 Canvas 导出')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)
    ctx.drawImage(img, 0, 0, width, height)
    return await canvasToBlob(canvas)
  }
  finally {
    URL.revokeObjectURL(url)
  }
}

defineExpose({
  toPngBlob,
})

onMounted(() => {
  render()
  if (wrapRef.value) {
    resizeObserver = new ResizeObserver(() => fit())
    resizeObserver.observe(wrapRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  mm?.destroy()
  mm = null
})

watch(() => props.markdown, render)

</script>

<template>
  <div ref="wrapRef" class="w-full h-full min-h-[360px] bg-white rounded border overflow-hidden">
    <svg ref="svgRef" class="w-full h-full min-h-[360px]" />
  </div>
</template>
