<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getProviders, ping } from '~/logic/api'
import { settings, settingsReady } from '~/logic/storage'
import { getModelsByProvider } from '~/logic/api'
import type { Model, Provider } from '~/logic/types'
import { watch } from 'vue'

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
          <input v-model="settings.style" class="input" placeholder="留空使用默认">
        </label>
        <label class="flex items-center gap-2">
          <input v-model="settings.screenshot" type="checkbox"> 自动插入截图
        </label>
        <label class="flex items-center gap-2">
          <input v-model="settings.link" type="checkbox"> 插入原片跳转链接
        </label>
      </div>
    </section>
  </div>
</template>
