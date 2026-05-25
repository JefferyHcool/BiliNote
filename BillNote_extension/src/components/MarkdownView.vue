<script setup lang="ts">
import { computed, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import { absolutizeMarkdownImages, stripSourceLink } from '~/logic/api'

const props = defineProps<{ markdown: string, title?: string, hideActions?: boolean }>()

const contentRef = ref<HTMLElement | null>(null)

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value)
  }
  catch {
    return value
  }
}

function slugify(value: string): string {
  const slug = safeDecode(value)
    .trim()
    .toLowerCase()
    .replace(/[`*_~[\](){}<>]/g, '')
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  return slug || 'section'
}

function normalizeAnchor(value: string): string {
  return safeDecode(value)
    .replace(/^#+/, '')
    .replace(/content-\d{1,2}:\d{2}(?::\d{2})?/gi, '')
    .replace(/\[[^\]]*\]/g, '')
    .replace(/[`*_~()[\]{}<>]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '')
    .toLowerCase()
}

md.renderer.rules.heading_open = (tokens, idx, options, env, self) => {
  const text = tokens[idx + 1]?.content || ''
  const base = slugify(text)
  const headingCounts = (env.headingCounts ||= {}) as Record<string, number>
  const count = headingCounts[base] || 0
  headingCounts[base] = count + 1
  tokens[idx].attrSet('id', count ? `${base}-${count}` : base)
  return self.renderToken(tokens, idx, options)
}

const html = computed(() => {
  const env: { headingCounts: Record<string, number> } = { headingCounts: {} }
  return md.render(absolutizeMarkdownImages(stripSourceLink(props.markdown || '')), env)
})

function findAnchorTarget(href: string): HTMLElement | null {
  const root = contentRef.value
  if (!root)
    return null

  const raw = safeDecode(href.replace(/^#/, ''))
  const byId = Array.from(root.querySelectorAll<HTMLElement>('[id]'))
  let target = byId.find(el => el.id === raw || safeDecode(el.id) === raw || el.id === slugify(raw))
  if (target)
    return target

  const search = normalizeAnchor(raw)
  if (!search)
    return null

  const headings = Array.from(root.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5, h6'))
  target = headings.find((heading) => {
    const text = normalizeAnchor(heading.textContent || '')
    return !!text && (text.includes(search) || search.includes(text))
  })

  return target || null
}

function handleContentClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element))
    return

  const link = target.closest<HTMLAnchorElement>('a[href^="#"]')
  if (!link || !contentRef.value?.contains(link))
    return

  event.preventDefault()
  const heading = findAnchorTarget(link.getAttribute('href') || '')
  if (heading)
    heading.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function copy() {
  await navigator.clipboard.writeText(props.markdown)
}

function download() {
  const blob = new Blob([props.markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${props.title || 'bilinote'}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="flex flex-col gap-2 h-full">
    <div v-if="!hideActions" class="flex gap-2 justify-end shrink-0">
      <button class="btn-secondary" @click="copy">复制 Markdown</button>
      <button class="btn-secondary" @click="download">下载 .md</button>
    </div>
    <div
      ref="contentRef"
      class="prose prose-sm max-w-none px-3 py-2 flex-1 min-h-0 overflow-auto"
      @click="handleContentClick"
      v-html="html"
    />
  </div>
</template>

<style>
.prose img { max-width: 100%; }
.prose h1, .prose h2, .prose h3 { font-weight: 600; margin-top: 0.8em; margin-bottom: 0.4em; }
.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6 { scroll-margin-top: 0.75rem; }
.prose p { margin-bottom: 0.5em; line-height: 1.55; }
.prose ul, .prose ol { padding-left: 1.4em; margin-bottom: 0.5em; }
.prose code { background: #eee; padding: 0 4px; border-radius: 3px; font-size: 0.9em; }
.prose a { color: #2563eb; text-decoration: underline; }
</style>
