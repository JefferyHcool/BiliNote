<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { askChat, getChatStatus, indexChatTask, type ChatMessage } from '~/logic/api'
import { settings } from '~/logic/storage'

const props = defineProps<{ taskId: string }>()

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const messages = ref<ChatMessage[]>([])
const draft = ref('')
const sending = ref(false)
const indexState = ref<'idle' | 'indexing' | 'indexed' | 'failed' | 'unknown'>('unknown')
const error = ref('')
const scrollEl = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const ready = computed(() => indexState.value === 'indexed')
const canSend = computed(() => ready.value && draft.value.trim().length > 0 && !sending.value && !!settings.value.providerId && !!settings.value.modelName)

async function pollIndex() {
  try {
    const res = await getChatStatus(props.taskId)
    indexState.value = res.status
    if (res.status === 'indexing')
      pollTimer = setTimeout(pollIndex, 2000)
  }
  catch (e) {
    error.value = (e as Error).message
    indexState.value = 'failed'
  }
}

async function ensureIndexed() {
  error.value = ''
  indexState.value = 'unknown'
  try {
    const status = await getChatStatus(props.taskId)
    indexState.value = status.status
    if (status.indexed)
      return
    indexState.value = 'indexing'
    await indexChatTask(props.taskId)
    pollIndex()
  }
  catch (e) {
    error.value = (e as Error).message
    indexState.value = 'failed'
  }
}

async function send() {
  if (!canSend.value)
    return
  const question = draft.value.trim()
  draft.value = ''
  messages.value.push({ role: 'user', content: question })
  await scrollDown()
  sending.value = true
  try {
    const res = await askChat({
      task_id: props.taskId,
      question,
      history: messages.value.slice(0, -1),
      provider_id: settings.value.providerId,
      model_name: settings.value.modelName,
    }) as { answer?: string, content?: string, message?: string } | string
    const reply = typeof res === 'string'
      ? res
      : (res.answer ?? res.content ?? res.message ?? JSON.stringify(res))
    messages.value.push({ role: 'assistant', content: reply })
    await scrollDown()
  }
  catch (e) {
    messages.value.push({ role: 'assistant', content: `❌ 调用失败：${(e as Error).message}` })
  }
  finally {
    sending.value = false
  }
}

async function scrollDown() {
  await nextTick()
  if (scrollEl.value)
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

watch(() => props.taskId, () => {
  messages.value = []
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  ensureIndexed()
}, { immediate: false })

onMounted(ensureIndexed)
onUnmounted(() => {
  if (pollTimer)
    clearTimeout(pollTimer)
})
</script>

<template>
  <div class="flex flex-col h-full bg-white">
    <header class="px-2 py-1 text-xs border-b flex items-center gap-2">
      <span v-if="indexState === 'indexed'" class="tag bg-green-100 text-green-700">已索引</span>
      <span v-else-if="indexState === 'indexing'" class="tag bg-yellow-100 text-yellow-700">索引中…</span>
      <span v-else-if="indexState === 'failed'" class="tag bg-red-100 text-red-700">索引失败</span>
      <span v-else class="tag bg-gray-100 text-gray-500">检查中…</span>
      <button class="ml-auto text-xs text-gray-500 hover:text-gray-800" @click="ensureIndexed">
        重新索引
      </button>
    </header>

    <div v-if="error" class="text-xs text-red-600 px-2 py-1">{{ error }}</div>

    <div ref="scrollEl" class="flex-1 overflow-auto px-2 py-2 flex flex-col gap-2">
      <div v-if="messages.length === 0 && ready" class="text-xs text-gray-400 italic">
        基于这条笔记的全文 + 视频元信息提问，例如：「这个视频的核心论点是什么？」
      </div>
      <div
        v-for="(m, i) in messages"
        :key="i"
        class="text-sm"
      >
        <div
          class="inline-block max-w-[90%] px-3 py-2 rounded"
          :class="m.role === 'user'
            ? 'bg-blue-600 text-white ml-auto block'
            : 'bg-gray-100 text-gray-800'"
        >
          <div v-if="m.role === 'assistant'" v-html="md.render(m.content)" class="prose prose-sm max-w-none" />
          <div v-else class="whitespace-pre-wrap break-words">{{ m.content }}</div>
        </div>
      </div>
      <div v-if="sending" class="text-xs text-gray-500 italic">思考中…</div>
    </div>

    <footer class="border-t p-2 flex gap-2">
      <textarea
        v-model="draft"
        class="input flex-1 resize-none"
        rows="2"
        :placeholder="ready ? '问点什么…（Cmd/Ctrl + Enter 发送）' : '索引完成后才能问答'"
        :disabled="!ready"
        @keydown.enter.exact.meta.prevent="send"
        @keydown.enter.exact.ctrl.prevent="send"
      />
      <button class="btn-primary" :disabled="!canSend" @click="send">
        {{ sending ? '…' : '发送' }}
      </button>
    </footer>
  </div>
</template>
