<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { detectPlatform } from '~/logic/platform'
import { settings, settingsReady, tasks, tasksReady, upsertTask } from '~/logic/storage'
import { generateNote, getTaskStatus } from '~/logic/api'
import type { TaskRecord } from '~/logic/types'

const tabUrl = ref<string>('')
const tabTitle = ref<string>('')
const platform = computed(() => detectPlatform(tabUrl.value))
const supported = computed(() => platform.value !== null)

const submitting = ref(false)
const errorMsg = ref('')
const activeTaskId = ref<string>('')
const activeTask = computed<TaskRecord | undefined>(() => tasks.value?.find(t => t.taskId === activeTaskId.value))

let pollTimer: ReturnType<typeof setTimeout> | null = null

async function loadActiveTab() {
  try {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true })
    tabUrl.value = tab?.url ?? ''
    tabTitle.value = tab?.title ?? ''
  }
  catch (e) {
    console.warn('无法读取当前 tab:', e)
  }
}

async function poll(taskId: string) {
  try {
    const res = await getTaskStatus(taskId)
    upsertTask({
      taskId,
      videoUrl: activeTask.value?.videoUrl ?? tabUrl.value,
      platform: (activeTask.value?.platform ?? platform.value)!,
      status: res.status,
      message: res.message,
      createdAt: activeTask.value?.createdAt ?? Date.now(),
      updatedAt: Date.now(),
      result: res.result ?? activeTask.value?.result,
    })
    if (res.status !== 'SUCCESS' && res.status !== 'FAILED')
      pollTimer = setTimeout(() => poll(taskId), 3000)
  }
  catch (e) {
    errorMsg.value = (e as Error).message
    pollTimer = setTimeout(() => poll(taskId), 5000)
  }
}

async function start() {
  errorMsg.value = ''
  if (!supported.value) {
    errorMsg.value = '当前页面不是支持的视频链接'
    return
  }
  if (!settings.value.providerId || !settings.value.modelName) {
    errorMsg.value = '请先去设置页选择供应商和模型'
    return
  }
  submitting.value = true
  try {
    const { task_id } = await generateNote({
      video_url: tabUrl.value,
      platform: platform.value!,
      quality: settings.value.quality,
      provider_id: settings.value.providerId,
      model_name: settings.value.modelName,
      screenshot: settings.value.screenshot,
      link: settings.value.link,
      style: settings.value.style || undefined,
      format: [
        ...(settings.value.screenshot ? ['screenshot'] : []),
        ...(settings.value.link ? ['link'] : []),
      ],
    })
    activeTaskId.value = task_id
    upsertTask({
      taskId: task_id,
      videoUrl: tabUrl.value,
      platform: platform.value!,
      status: 'PENDING',
      message: '已提交',
      createdAt: Date.now(),
      updatedAt: Date.now(),
    })
    poll(task_id)
  }
  catch (e) {
    errorMsg.value = (e as Error).message
  }
  finally {
    submitting.value = false
  }
}

function openOptions() {
  browser.runtime.openOptionsPage()
}

function selectTask(id: string) {
  activeTaskId.value = id
  const t = tasks.value?.find(x => x.taskId === id)
  if (t && t.status !== 'SUCCESS' && t.status !== 'FAILED')
    poll(id)
}

onMounted(async () => {
  await Promise.all([settingsReady, tasksReady])
  await loadActiveTab()
  // 如果有进行中的任务，恢复轮询
  const running = tasks.value?.find(t => t.status !== 'SUCCESS' && t.status !== 'FAILED')
  if (running) {
    activeTaskId.value = running.taskId
    poll(running.taskId)
  }
})

onUnmounted(() => {
  if (pollTimer)
    clearTimeout(pollTimer)
})
</script>

<template>
  <main class="w-[400px] p-3 text-sm text-gray-800 flex flex-col gap-3 bg-white">
    <header class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="font-semibold text-base">BiliNote</span>
        <PlatformBadge :platform="platform" />
      </div>
      <button class="text-xs text-gray-500 hover:text-gray-800" @click="openOptions">设置</button>
    </header>

    <div class="text-xs text-gray-500 truncate" :title="tabUrl">
      {{ tabUrl || '当前没有打开的标签页' }}
    </div>

    <div v-if="!supported" class="text-xs text-amber-700 bg-amber-50 p-2 rounded">
      当前页面不是 BiliNote 支持的视频链接（Bilibili / YouTube / Douyin / Kuaishou）
    </div>

    <fieldset class="border rounded p-2 flex flex-col gap-2" :disabled="!supported || submitting">
      <div class="grid grid-cols-3 gap-2 text-xs">
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">画质</span>
          <select v-model="settings.quality" class="border rounded px-1 py-0.5">
            <option value="fast">快速</option>
            <option value="medium">中等</option>
            <option value="slow">高质</option>
          </select>
        </label>
        <label class="flex items-center gap-1 mt-4">
          <input v-model="settings.screenshot" type="checkbox"> 截图
        </label>
        <label class="flex items-center gap-1 mt-4">
          <input v-model="settings.link" type="checkbox"> 跳转
        </label>
      </div>

      <div class="text-xs text-gray-600">
        <span v-if="settings.providerId && settings.modelName">
          模型：{{ settings.modelName }}
        </span>
        <span v-else class="text-amber-700">
          ⚠ 未选择供应商/模型，
          <button class="underline" @click="openOptions">去设置</button>
        </span>
      </div>

      <button class="btn-primary" :disabled="!supported || submitting || !settings.providerId" @click="start">
        {{ submitting ? '提交中…' : '生成笔记' }}
      </button>
    </fieldset>

    <div v-if="errorMsg" class="text-xs text-red-600 break-words">
      {{ errorMsg }}
    </div>

    <section v-if="activeTask" class="flex flex-col gap-2">
      <TaskProgress :status="activeTask.status" :message="activeTask.message" />
      <MarkdownView
        v-if="activeTask.status === 'SUCCESS' && activeTask.result?.markdown"
        :markdown="activeTask.result.markdown"
        :title="activeTask.result.audio_meta?.title || tabTitle"
      />
    </section>

    <details v-if="(tasks?.length ?? 0) > 0" class="text-xs">
      <summary class="cursor-pointer text-gray-500">最近任务（{{ tasks!.length }}）</summary>
      <ul class="mt-1 flex flex-col gap-1 max-h-32 overflow-auto">
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

<style>
.btn-primary { @apply bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm; }
.btn-secondary { @apply bg-gray-100 text-gray-700 px-2 py-1 rounded hover:bg-gray-200 text-xs; }
</style>
