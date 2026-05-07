<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getProviders, ping } from '~/logic/api'
import { settings, settingsReady } from '~/logic/storage'
import { getModelsByProvider } from '~/logic/api'
import { NOTE_FORMATS, NOTE_STYLES, type Model, type NoteFormat, type Provider } from '~/logic/types'
import { watch } from 'vue'

function toggleFormat(value: NoteFormat, checked: boolean) {
  const cur = settings.value.formats || []
  settings.value.formats = checked
    ? Array.from(new Set([...cur, value]))
    : cur.filter(v => v !== value)
}

const providers = ref<Provider[]>([])
const models = ref<Model[]>([])
const status = ref<{ kind: 'idle' | 'ok' | 'err', text: string }>({ kind: 'idle', text: '' })
const loading = ref(false)

async function refresh() {
  loading.value = true
  status.value = { kind: 'idle', text: '' }
  try {
    providers.value = (await getProviders()).filter(p => p.enabled === 1)
    if (settings.value.providerId)
      await refreshModels(settings.value.providerId)
    status.value = { kind: 'ok', text: `已加载 ${providers.value.length} 个供应商` }
  }
  catch (e) {
    status.value = { kind: 'err', text: `加载失败：${(e as Error).message}` }
    providers.value = []
    models.value = []
  }
  finally {
    loading.value = false
  }
}

async function refreshModels(providerId: string) {
  if (!providerId) {
    models.value = []
    return
  }
  try {
    models.value = await getModelsByProvider(providerId)
  }
  catch {
    models.value = []
  }
}

async function testConnection() {
  status.value = { kind: 'idle', text: '正在测试…' }
  const ok = await ping()
  status.value = ok
    ? { kind: 'ok', text: '后端连通 ✓' }
    : { kind: 'err', text: '无法连接后端，请检查地址、端口与 CORS' }
}

watch(() => settings.value?.providerId, (id) => {
  if (id)
    refreshModels(id)
})

onMounted(async () => {
  await settingsReady
  if (settings.value.backendUrl)
    await refresh()
})
</script>

<template>
  <div class="p-6 max-w-2xl">
    <h1 class="text-xl font-bold mb-4">通用</h1>

    <section class="section-card">
      <h2 class="font-semibold">后端地址</h2>
      <div class="flex gap-2">
        <input v-model="settings.backendUrl" class="input flex-1" placeholder="http://localhost:8483">
        <button class="btn-secondary" @click="testConnection">测试连通</button>
        <button class="btn-secondary" :disabled="loading" @click="refresh">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
      </div>
      <div
        v-if="status.text"
        class="text-xs"
        :class="{
          'text-green-700': status.kind === 'ok',
          'text-red-600': status.kind === 'err',
          'text-gray-500': status.kind === 'idle',
        }"
      >
        {{ status.text }}
      </div>
      <p class="text-xs text-gray-500">
        默认 http://localhost:8483 — 需要在该地址先跑起 BiliNote 后端
      </p>
    </section>

    <section class="section-card">
      <h2 class="font-semibold">默认供应商与模型</h2>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">供应商</span>
        <select v-model="settings.providerId" class="input">
          <option value="">— 选择供应商 —</option>
          <option v-for="p in providers" :key="p.id" :value="p.id">
            {{ p.name }} <span v-if="p.type === 'built-in'">(内置)</span>
          </option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">模型</span>
        <select v-model="settings.modelName" class="input" :disabled="!settings.providerId">
          <option value="">— 选择模型 —</option>
          <option v-for="m in models" :key="m.id" :value="m.model_name">{{ m.model_name }}</option>
        </select>
        <span v-if="settings.providerId && models.length === 0" class="text-xs text-amber-700">
          该供应商还没添加可用模型，去「模型供应商」页编辑
        </span>
      </label>
    </section>

    <section class="section-card">
      <h2 class="font-semibold">默认生成选项</h2>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">画质</span>
          <select v-model="settings.quality" class="input">
            <option value="fast">快速 (32k)</option>
            <option value="medium">中等 (64k)</option>
            <option value="slow">高质 (128k)</option>
          </select>
        </label>
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">笔记风格</span>
          <select v-model="settings.style" class="input">
            <option v-for="s in NOTE_STYLES" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </label>
      </div>

      <div class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">输出形式（与 web 端 NoteForm 对齐）</span>
        <div class="flex flex-wrap gap-x-4 gap-y-2">
          <label v-for="f in NOTE_FORMATS" :key="f.value" class="flex items-center gap-2">
            <input
              type="checkbox"
              :checked="(settings.formats || []).includes(f.value)"
              @change="toggleFormat(f.value, ($event.target as HTMLInputElement).checked)"
            >
            {{ f.label }}
          </label>
        </div>
      </div>

      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">额外提示词（追加到 prompt 末尾）</span>
        <textarea
          v-model="settings.extras"
          class="input resize-y"
          rows="3"
          placeholder="例如：重点关注游戏开发部分；保留所有专业术语原文"
        />
      </label>
    </section>

    <section class="section-card">
      <h2 class="font-semibold">视频理解（多模态）</h2>
      <p class="text-xs text-gray-500">
        启用后会按抽帧间隔截取视频帧拼成网格图，连同字幕一起喂给视觉模型，提升画面相关问题的回答质量。
        <strong class="text-amber-700">需要选择视觉模型</strong>（GPT-4o / Gemini / Claude 等），文字模型会忽略图片。
      </p>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="settings.video_understanding" type="checkbox">
        启用视频理解
      </label>
      <div v-if="settings.video_understanding" class="grid grid-cols-3 gap-3 text-sm">
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">抽帧间隔(秒, 1-30)</span>
          <input v-model.number="settings.video_interval" type="number" min="1" max="30" class="input">
        </label>
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">拼图行 (1-10)</span>
          <input
            :value="settings.grid_size?.[0] ?? 2"
            type="number" min="1" max="10" class="input"
            @input="settings.grid_size = [Number(($event.target as HTMLInputElement).value) || 2, settings.grid_size?.[1] ?? 2]"
          >
        </label>
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">拼图列 (1-10)</span>
          <input
            :value="settings.grid_size?.[1] ?? 2"
            type="number" min="1" max="10" class="input"
            @input="settings.grid_size = [settings.grid_size?.[0] ?? 2, Number(($event.target as HTMLInputElement).value) || 2]"
          >
        </label>
      </div>
    </section>
  </div>
</template>
