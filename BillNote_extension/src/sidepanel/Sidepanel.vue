<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getTaskStatus, resolveImageUrl } from '~/logic/api'
import { tasks, tasksReady, settingsReady, upsertTask } from '~/logic/storage'
import type { TaskRecord } from '~/logic/types'
import { getTaskDisplayTitle } from '~/logic/task-display'

type ViewMode = 'markdown' | 'mindmap' | 'chat'

const activeTaskId = ref<string>('')
const activeTask = computed<TaskRecord | undefined>(() => tasks.value?.find(t => t.taskId === activeTaskId.value))
const errorMsg = ref('')
const successMsg = ref('')
const viewMode = ref<ViewMode>('markdown')
const showHistory = ref(false)
const mindMapRef = ref<{ toPngBlob: () => Promise<Blob> } | null>(null)

const isDone = computed(() => activeTask.value?.status === 'SUCCESS')
const isFailed = computed(() => activeTask.value?.status === 'FAILED')
const isRunning = computed(() => !!activeTask.value && !isDone.value && !isFailed.value)

const STAGE_LABELS: Record<string, string> = {
  PENDING: '排队中',
  PARSING: '解析中',
  DOWNLOADING: '下载中',
  TRANSCRIBING: '转写中',
  SUMMARIZING: '总结中',
  FORMATTING: '格式化',
  SAVING: '保存中',
  SUCCESS: '完成',
  FAILED: '失败',
}

let pollTimer: ReturnType<typeof setTimeout> | null = null

async function poll(taskId: string) {
  try {
    const res = await getTaskStatus(taskId)
    const cur = tasks.value?.find(t => t.taskId === taskId)
    if (cur) {
      upsertTask({
        ...cur,
        status: res.status,
        message: res.message,
        result: res.result ?? cur.result,
        updatedAt: Date.now(),
        title: cur.title || getTaskDisplayTitle(cur),
      })
    }
    if (res.status !== 'SUCCESS' && res.status !== 'FAILED')
      pollTimer = setTimeout(() => poll(taskId), 3000)
  }
  catch (e) {
    errorMsg.value = (e as Error).message
    pollTimer = setTimeout(() => poll(taskId), 5000)
  }
}

function selectTask(id: string) {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  activeTaskId.value = id
  showHistory.value = false
  const t = tasks.value?.find(x => x.taskId === id)
  if (t && t.status !== 'SUCCESS' && t.status !== 'FAILED')
    poll(id)
}

function openOptions() {
  browser.runtime.openOptionsPage()
}

async function copyMarkdown() {
  const md = activeTask.value?.result?.markdown
  if (md)
    await navigator.clipboard.writeText(md)
}

function safeFilename(name: string): string {
  return (name || 'bilinote')
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120) || 'bilinote'
}

function downloadMarkdown() {
  const md = activeTask.value?.result?.markdown
  if (!md)
    return
  const title = safeFilename(getTaskDisplayTitle(activeTask.value))
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title}.md`
  a.click()
  URL.revokeObjectURL(url)
}

async function copyMindMapImage() {
  try {
    errorMsg.value = ''
    successMsg.value = ''
    const blob = await mindMapRef.value?.toPngBlob()
    if (!blob)
      return
    await navigator.clipboard.write([
      new ClipboardItem({ [blob.type]: blob }),
    ])
    successMsg.value = '思维导图图片已复制'
    setTimeout(() => { successMsg.value = '' }, 2000)
  }
  catch (e) {
    errorMsg.value = (e as Error).message || '复制思维导图图片失败'
  }
}

async function downloadMindMapImage() {
  try {
    errorMsg.value = ''
    successMsg.value = ''
    const blob = await mindMapRef.value?.toPngBlob()
    if (!blob)
      return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${safeFilename(getTaskDisplayTitle(activeTask.value))}.png`
    a.click()
    URL.revokeObjectURL(url)
  }
  catch (e) {
    errorMsg.value = (e as Error).message || '下载思维导图图片失败'
  }
}

const activeTitle = computed(() => getTaskDisplayTitle(activeTask.value))

const activeCover = computed(() =>
  (activeTask.value?.result?.audio_meta as { cover_url?: string } | undefined)?.cover_url)

onMounted(async () => {
  await Promise.all([settingsReady, tasksReady])
  const latest = tasks.value?.[0]
  if (latest) {
    activeTaskId.value = latest.taskId
    if (latest.status !== 'SUCCESS' && latest.status !== 'FAILED')
      poll(latest.taskId)
  }
})

onUnmounted(() => {
  if (pollTimer)
    clearTimeout(pollTimer)
})
</script>

<template>
  <main class="w-full h-full flex flex-col bg-white text-sm text-gray-800">
    <!-- 顶栏：极简 -->
    <header class="flex items-center justify-between px-3 py-2 border-b shrink-0">
      <div class="font-semibold">BiliNote</div>
      <div class="flex items-center gap-1">
        <button
          v-if="(tasks?.length ?? 0) > 0"
          class="text-xs text-gray-500 hover:text-gray-800 px-2 py-0.5 rounded hover:bg-gray-100"
          :class="{ 'bg-gray-100': showHistory }"
          @click="showHistory = !showHistory"
        >
          历史 {{ tasks?.length }}
        </button>
        <button class="text-xs text-gray-500 hover:text-gray-800 px-2 py-0.5 rounded hover:bg-gray-100" @click="openOptions">
          设置
        </button>
      </div>
    </header>

    <!-- 历史弹层（覆盖在内容上方） -->
    <div v-if="showHistory" class="border-b bg-gray-50 px-2 py-2 max-h-60 overflow-auto shrink-0">
      <ul class="flex flex-col gap-0.5 text-xs">
        <li
          v-for="t in tasks"
          :key="t.taskId"
          class="flex items-center gap-2 px-2 py-1 rounded cursor-pointer hover:bg-white"
          :class="{ 'bg-white border': t.taskId === activeTaskId }"
          @click="selectTask(t.taskId)"
        >
          <span class="truncate flex-1" :title="getTaskDisplayTitle(t)">
            {{ getTaskDisplayTitle(t) }}
          </span>
          <span class="text-gray-400 shrink-0">{{ STAGE_LABELS[t.status] || t.status }}</span>
        </li>
      </ul>
    </div>

    <div v-if="errorMsg" class="text-xs text-red-600 px-3 py-1 break-words bg-red-50 shrink-0">
      {{ errorMsg }}
    </div>
    <div v-if="successMsg" class="text-xs text-green-700 px-3 py-1 break-words bg-green-50 shrink-0">
      {{ successMsg }}
    </div>

    <section v-if="!activeTask" class="flex-1 flex items-center justify-center text-gray-400 text-xs px-4 text-center">
      还没有任务。在视频页点悬浮按钮、在 popup 提交，或右键菜单选「用 BiliNote 总结」。
    </section>

    <section v-else class="flex-1 flex flex-col min-h-0">
      <!-- 标题区：紧凑一行 -->
      <div class="flex items-center gap-2 px-3 py-2 border-b shrink-0">
        <img
          v-if="activeCover"
          :src="resolveImageUrl(activeCover)"
          class="w-12 h-7 object-cover rounded bg-gray-100 shrink-0"
          alt=""
          @error="($event.target as HTMLImageElement).style.display = 'none'"
        >
        <a
          class="text-sm font-medium leading-tight line-clamp-1 break-all flex-1 min-w-0 hover:text-blue-600"
          :href="activeTask.videoUrl"
          target="_blank"
          :title="activeTitle || activeTask.videoUrl"
        >{{ activeTitle }}</a>
        <span
          v-if="isDone"
          class="text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-700 shrink-0"
          title="完成"
        >✓</span>
        <span
          v-else-if="isFailed"
          class="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700 shrink-0"
          :title="activeTask.message"
        >失败</span>
        <span
          v-else
          class="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 shrink-0 animate-pulse"
        >{{ STAGE_LABELS[activeTask.status] || activeTask.status }}</span>
      </div>

      <!-- 进行中：进度条；完成：tab + 操作按钮 -->
      <div v-if="isRunning" class="px-3 py-2 border-b shrink-0">
        <TaskProgress :status="activeTask.status" :message="activeTask.message" />
      </div>
      <div
        v-else-if="isDone && activeTask.result?.markdown"
        class="flex items-center gap-1 px-2 py-1.5 border-b shrink-0 text-xs"
      >
        <button
          class="px-2 py-1 rounded"
          :class="viewMode === 'markdown' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 text-gray-700'"
          @click="viewMode = 'markdown'"
        >Markdown</button>
        <button
          class="px-2 py-1 rounded"
          :class="viewMode === 'mindmap' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 text-gray-700'"
          @click="viewMode = 'mindmap'"
        >思维导图</button>
        <button
          class="px-2 py-1 rounded"
          :class="viewMode === 'chat' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 text-gray-700'"
          @click="viewMode = 'chat'"
        >AI 问答</button>
        <div class="flex-1" />
        <button
          v-if="viewMode === 'markdown'"
          class="text-gray-500 hover:text-gray-800 px-1.5 py-1 rounded hover:bg-gray-100"
          title="复制 Markdown"
          @click="copyMarkdown"
        >复制</button>
        <button
          v-if="viewMode === 'markdown'"
          class="text-gray-500 hover:text-gray-800 px-1.5 py-1 rounded hover:bg-gray-100"
          title="下载 .md"
          @click="downloadMarkdown"
        >下载</button>
        <button
          v-if="viewMode === 'mindmap'"
          class="text-gray-500 hover:text-gray-800 px-1.5 py-1 rounded hover:bg-gray-100"
          title="复制思维导图图片"
          @click="copyMindMapImage"
        >复制</button>
        <button
          v-if="viewMode === 'mindmap'"
          class="text-gray-500 hover:text-gray-800 px-1.5 py-1 rounded hover:bg-gray-100"
          title="下载思维导图 PNG"
          @click="downloadMindMapImage"
        >下载</button>
      </div>

      <!-- 内容区：占满剩余空间 -->
      <div class="flex-1 overflow-auto min-h-0">
        <MarkdownView
          v-if="isDone && activeTask.result?.markdown && viewMode === 'markdown'"
          :markdown="activeTask.result.markdown"
          :title="(activeTask.result.audio_meta as { title?: string } | undefined)?.title"
          :hide-actions="true"
        />
        <MindMap
          v-else-if="isDone && activeTask.result?.markdown && viewMode === 'mindmap'"
          ref="mindMapRef"
          :markdown="activeTask.result.markdown"
          class="h-full"
        />
        <ChatPanel
          v-else-if="isDone && viewMode === 'chat'"
          :task-id="activeTask.taskId"
          class="h-full"
        />
        <div v-else-if="isFailed" class="p-4 text-sm text-red-600">
          {{ activeTask.message || '任务失败' }}
        </div>
      </div>
    </section>
  </main>
</template>

<style>
.line-clamp-1 { display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>
