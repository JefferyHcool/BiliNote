<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getTaskStatus } from '~/logic/api'
import { settings, settingsReady, tasks, tasksReady, upsertTask } from '~/logic/storage'
import type { TaskRecord } from '~/logic/types'

type ViewMode = 'markdown' | 'mindmap' | 'chat'

const activeTaskId = ref<string>('')
const activeTask = computed<TaskRecord | undefined>(() => tasks.value?.find(t => t.taskId === activeTaskId.value))
const errorMsg = ref('')
const viewMode = ref<ViewMode>('markdown')

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
  const t = tasks.value?.find(x => x.taskId === id)
  if (t && t.status !== 'SUCCESS' && t.status !== 'FAILED')
    poll(id)
}

function openOptions() {
  browser.runtime.openOptionsPage()
}

onMounted(async () => {
  await Promise.all([settingsReady, tasksReady])
  // 默认选中最近的任务（无论是否完成）
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
    <header class="flex items-center justify-between px-3 py-2 border-b">
      <div class="font-semibold">BiliNote 侧边栏</div>
      <button class="text-xs text-gray-500 hover:text-gray-800" @click="openOptions">设置</button>
    </header>

    <div v-if="errorMsg" class="text-xs text-red-600 px-3 py-2 break-words bg-red-50">
      {{ errorMsg }}
    </div>

    <section v-if="!activeTask" class="flex-1 flex items-center justify-center text-gray-400 text-xs px-4 text-center">
      还没有任务。在视频页点悬浮按钮、在 popup 提交，或右键菜单选「用 BiliNote 总结」。
    </section>

    <section v-else class="flex-1 flex flex-col gap-3 p-3 overflow-hidden">
      <div class="text-xs text-gray-500 truncate" :title="activeTask.videoUrl">
        {{ activeTask.videoUrl }}
      </div>
      <TaskProgress :status="activeTask.status" :message="activeTask.message" />

      <div v-if="activeTask.status === 'SUCCESS' && activeTask.result?.markdown" class="flex gap-1 text-xs">
        <button
          class="px-2 py-1 rounded"
          :class="viewMode === 'markdown' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
          @click="viewMode = 'markdown'"
        >Markdown</button>
        <button
          class="px-2 py-1 rounded"
          :class="viewMode === 'mindmap' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
          @click="viewMode = 'mindmap'"
        >思维导图</button>
        <button
          class="px-2 py-1 rounded"
          :class="viewMode === 'chat' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
          @click="viewMode = 'chat'"
        >AI 问答</button>
      </div>

      <div class="flex-1 overflow-auto min-h-0">
        <MarkdownView
          v-if="activeTask.status === 'SUCCESS' && activeTask.result?.markdown && viewMode === 'markdown'"
          :markdown="activeTask.result.markdown"
          :title="activeTask.result.audio_meta?.title"
        />
        <MindMap
          v-else-if="activeTask.status === 'SUCCESS' && activeTask.result?.markdown && viewMode === 'mindmap'"
          :markdown="activeTask.result.markdown"
          class="h-full"
        />
        <ChatPanel
          v-else-if="activeTask.status === 'SUCCESS' && viewMode === 'chat'"
          :task-id="activeTask.taskId"
          class="h-full"
        />
      </div>
    </section>

    <details v-if="(tasks?.length ?? 0) > 1" class="text-xs border-t px-3 py-2">
      <summary class="cursor-pointer text-gray-500">
        历史任务（{{ tasks!.length }}）
      </summary>
      <ul class="mt-1 flex flex-col gap-1 max-h-40 overflow-auto">
        <li
          v-for="t in tasks"
          :key="t.taskId"
          class="flex justify-between items-center gap-2 px-1 py-0.5 rounded hover:bg-gray-100 cursor-pointer"
          :class="{ 'bg-blue-50': t.taskId === activeTaskId }"
          @click="selectTask(t.taskId)"
        >
          <span class="truncate flex-1" :title="t.videoUrl">{{ t.result?.audio_meta?.title || t.videoUrl }}</span>
          <span class="text-gray-500">{{ t.status }}</span>
        </li>
      </ul>
    </details>
  </main>
</template>
