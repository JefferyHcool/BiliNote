<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { absolutizeMarkdownImages, stripSourceLink } from '~/logic/api'

const props = defineProps<{ markdown: string, title?: string, hideActions?: boolean }>()

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const html = computed(() => md.render(absolutizeMarkdownImages(stripSourceLink(props.markdown || ''))))

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
    <div class="prose prose-sm max-w-none px-3 py-2 flex-1 min-h-0 overflow-auto" v-html="html" />
  </div>
</template>

<style>
.prose img { max-width: 100%; }
.prose h1, .prose h2, .prose h3 { font-weight: 600; margin-top: 0.8em; margin-bottom: 0.4em; }
.prose p { margin-bottom: 0.5em; line-height: 1.55; }
.prose ul, .prose ol { padding-left: 1.4em; margin-bottom: 0.5em; }
.prose code { background: #eee; padding: 0 4px; border-radius: 3px; font-size: 0.9em; }
.prose a { color: #2563eb; text-decoration: underline; }
</style>
