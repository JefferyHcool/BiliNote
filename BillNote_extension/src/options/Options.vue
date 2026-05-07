<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { getModelsByProvider, getProviders, ping } from '~/logic/api'
import { settings, settingsReady } from '~/logic/storage'
import { SUPPORTED_COOKIE_PLATFORMS, syncCookieToBackend } from '~/logic/cookies'
import { PLATFORM_LABELS } from '~/logic/platform'
import type { Model, Platform, Provider } from '~/logic/types'

const providers = ref<Provider[]>([])
const models = ref<Model[]>([])
const loading = ref(false)
const status = ref<{ kind: 'idle' | 'ok' | 'err', text: string }>({ kind: 'idle', text: '' })

async function refreshProviders() {
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
    : { kind: 'err', text: '无法连接后端，请检查地址、端口与 CORS 配置' }
}

const cookieStatus = ref<Record<string, { kind: 'ok' | 'err' | 'idle', text: string }>>({})
const cookieBusy = ref<Record<string, boolean>>({})

async function syncCookie(platform: Exclude<Platform, 'local'>) {
  cookieBusy.value[platform] = true
  cookieStatus.value[platform] = { kind: 'idle', text: '同步中…' }
  const res = await syncCookieToBackend(platform)
  cookieStatus.value[platform] = res.ok
    ? { kind: 'ok', text: `已同步 ${res.count} 条 cookie ✓` }
    : { kind: 'err', text: res.error || '同步失败' }
  cookieBusy.value[platform] = false
}

watch(() => settings.value?.providerId, (id) => {
  if (id)
    refreshModels(id)
  // 切换供应商时清空已选模型，避免错配
  if (id !== providers.value.find(p => p.id === id)?.id)
    settings.value.modelName = ''
})

onMounted(async () => {
  await settingsReady
  if (settings.value.backendUrl)
    await refreshProviders()
})
</script>

<template>
  <main class="max-w-2xl mx-auto p-6 text-gray-800 dark:text-gray-100">
    <header class="flex items-center gap-2 mb-6">
      <h1 class="text-xl font-bold">BiliNote 浏览器插件 · 设置</h1>
    </header>

    <section class="bg-white dark:bg-gray-800 border rounded p-4 mb-4 flex flex-col gap-3">
      <h2 class="font-semibold">后端地址</h2>
      <div class="flex gap-2">
        <input
          v-model="settings.backendUrl"
          class="flex-1 border rounded px-2 py-1"
          placeholder="http://localhost:8483"
        >
        <button class="btn-secondary" @click="testConnection">测试连通</button>
        <button class="btn-secondary" :disabled="loading" @click="refreshProviders">
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
        默认 http://localhost:8483 — 需要在该地址先跑起 BiliNote 后端 (cd backend && python main.py)
      </p>
    </section>

    <section class="bg-white dark:bg-gray-800 border rounded p-4 mb-4 flex flex-col gap-3">
      <h2 class="font-semibold">默认供应商与模型</h2>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">供应商</span>
        <select v-model="settings.providerId" class="border rounded px-2 py-1">
          <option value="">— 选择供应商 —</option>
          <option v-for="p in providers" :key="p.id" :value="p.id">
            {{ p.name }} <span v-if="p.type === 'built-in'">(内置)</span>
          </option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-600">模型</span>
        <select v-model="settings.modelName" class="border rounded px-2 py-1" :disabled="!settings.providerId">
          <option value="">— 选择模型 —</option>
          <option v-for="m in models" :key="m.id" :value="m.model_name">{{ m.model_name }}</option>
        </select>
        <span v-if="settings.providerId && models.length === 0" class="text-xs text-amber-700">
          该供应商下还没有可用模型；请到桌面 web 端的「模型设置」里添加
        </span>
      </label>
    </section>

    <section class="bg-white dark:bg-gray-800 border rounded p-4 mb-4 flex flex-col gap-3">
      <h2 class="font-semibold">默认生成选项</h2>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">画质</span>
          <select v-model="settings.quality" class="border rounded px-2 py-1">
            <option value="fast">快速 (32k)</option>
            <option value="medium">中等 (64k)</option>
            <option value="slow">高质 (128k)</option>
          </select>
        </label>
        <label class="flex flex-col gap-1">
          <span class="text-gray-600">笔记风格</span>
          <input v-model="settings.style" class="border rounded px-2 py-1" placeholder="留空使用默认">
        </label>
        <label class="flex items-center gap-2">
          <input v-model="settings.screenshot" type="checkbox"> 自动插入截图
        </label>
        <label class="flex items-center gap-2">
          <input v-model="settings.link" type="checkbox"> 插入原片跳转链接
        </label>
      </div>
    </section>

    <section class="bg-white dark:bg-gray-800 border rounded p-4 mb-4 flex flex-col gap-3">
      <h2 class="font-semibold">浏览器 Cookie 同步</h2>
      <p class="text-xs text-gray-500">
        从当前浏览器读取你已登录站点的 cookie，并写入后端 (POST /api/update_downloader_cookie)。
        Bilibili / Douyin / Kuaishou 这类需要登录态的下载尤其需要这一步。
      </p>
      <div class="flex flex-col gap-2">
        <div
          v-for="p in SUPPORTED_COOKIE_PLATFORMS"
          :key="p"
          class="flex items-center justify-between gap-2 text-sm"
        >
          <span class="w-20">{{ PLATFORM_LABELS[p] }}</span>
          <button class="btn-secondary" :disabled="cookieBusy[p]" @click="syncCookie(p)">
            {{ cookieBusy[p] ? '同步中…' : '同步 Cookie' }}
          </button>
          <span
            class="flex-1 text-xs"
            :class="{
              'text-green-700': cookieStatus[p]?.kind === 'ok',
              'text-red-600': cookieStatus[p]?.kind === 'err',
              'text-gray-500': cookieStatus[p]?.kind === 'idle',
            }"
          >
            {{ cookieStatus[p]?.text || '' }}
          </span>
        </div>
      </div>
    </section>

    <p class="text-xs text-gray-500">
      所有设置自动保存。不在桌面端管理供应商/模型？请在 BiliNote web 端 (http://localhost:3015) 完成。
    </p>
  </main>
</template>

<style>
.btn-secondary { @apply bg-gray-100 text-gray-700 px-3 py-1 rounded hover:bg-gray-200 text-sm disabled:opacity-50; }
</style>
