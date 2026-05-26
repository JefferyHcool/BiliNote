<script setup lang="ts">
import 'uno.css'
import { computed, ref } from 'vue'
import { sendMessage } from 'webext-bridge/content-script'
import { detectPlatform, PLATFORM_LABELS } from '~/logic/platform'

const platform = detectPlatform(window.location.href)
const busy = ref(false)
const toast = ref<{ kind: 'ok' | 'err', text: string } | null>(null)

const label = computed(() => platform ? `用 BiliNote 总结这个${PLATFORM_LABELS[platform]}视频` : '')

async function trigger() {
  if (!platform || busy.value)
    return
  busy.value = true
  toast.value = null
  try {
    const res = await sendMessage('bilinote-start', {
      url: window.location.href,
      platform,
      title: document.title,
    }, 'background')
    const ok = res && (res as any).ok
    toast.value = ok
      ? { kind: 'ok', text: '已开始生成笔记，可在侧边栏 / popup 查看进度' }
      : { kind: 'err', text: (res as any)?.error || '提交失败，请打开设置检查后端与供应商' }
  }
  catch (e) {
    toast.value = { kind: 'err', text: (e as Error).message }
  }
  finally {
    busy.value = false
    setTimeout(() => { toast.value = null }, 4000)
  }
}
</script>

<template>
  <div v-if="platform" class="bilinote-fab fixed bottom-24 right-6 z-[2147483647] flex flex-col items-end gap-2 font-sans select-none">
    <div
      v-if="toast"
      class="text-xs px-3 py-2 rounded shadow max-w-[260px]"
      :class="toast.kind === 'ok' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
    >
      {{ toast.text }}
    </div>
    <button
      class="flex items-center gap-2 px-3 py-2 rounded-full shadow-lg cursor-pointer border-none text-white text-sm font-medium bg-pink-600 hover:bg-pink-700 disabled:bg-pink-300"
      :disabled="busy"
      :title="label"
      @click="trigger"
    >
      <span class="text-base">📝</span>
      <span>{{ busy ? '提交中…' : 'BiliNote' }}</span>
    </button>
  </div>
</template>
