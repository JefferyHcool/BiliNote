<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getDownloaderCookie, setDownloaderCookie } from '~/logic/api'
import { SUPPORTED_COOKIE_PLATFORMS, syncCookieToBackend } from '~/logic/cookies'
import { PLATFORM_LABELS } from '~/logic/platform'
import type { Platform } from '~/logic/types'

interface Row {
  cookie: string
  busy: boolean
  status: { kind: 'ok' | 'err' | 'idle', text: string }
}

const rows = reactive<Record<string, Row>>({})
const refreshing = ref(false)

function ensureRow(p: string) {
  if (!rows[p])
    rows[p] = { cookie: '', busy: false, status: { kind: 'idle', text: '' } }
  return rows[p]
}

async function refreshOne(p: Exclude<Platform, 'local'>) {
  const r = ensureRow(p)
  try {
    r.cookie = (await getDownloaderCookie(p)) ?? ''
  }
  catch (e) {
    r.status = { kind: 'err', text: `读取失败：${(e as Error).message}` }
  }
}

async function refreshAll() {
  refreshing.value = true
  await Promise.all(SUPPORTED_COOKIE_PLATFORMS.map(refreshOne))
  refreshing.value = false
}

async function syncFromBrowser(p: Exclude<Platform, 'local'>) {
  const r = ensureRow(p)
  r.busy = true
  r.status = { kind: 'idle', text: '从浏览器读取并同步…' }
  const res = await syncCookieToBackend(p)
  r.status = res.ok
    ? { kind: 'ok', text: `已同步 ${res.count} 条 cookie ✓` }
    : { kind: 'err', text: res.error || '同步失败' }
  if (res.ok)
    await refreshOne(p)
  r.busy = false
}

async function saveManual(p: Exclude<Platform, 'local'>) {
  const r = ensureRow(p)
  r.busy = true
  r.status = { kind: 'idle', text: '保存中…' }
  try {
    await setDownloaderCookie(p, r.cookie || '')
    r.status = { kind: 'ok', text: '已保存 ✓' }
  }
  catch (e) {
    r.status = { kind: 'err', text: `保存失败：${(e as Error).message}` }
  }
  finally {
    r.busy = false
  }
}

onMounted(() => {
  SUPPORTED_COOKIE_PLATFORMS.forEach(ensureRow)
  refreshAll()
})
</script>

<template>
  <div class="p-6 max-w-3xl">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-xl font-bold">下载配置</h1>
        <p class="text-xs text-gray-500 mt-1">
          每平台的 cookie 写入后端 (config/downloader.json)；下载时由对应 downloader 读取注入 yt-dlp。
        </p>
      </div>
      <button class="btn-secondary" :disabled="refreshing" @click="refreshAll">
        {{ refreshing ? '刷新中…' : '刷新' }}
      </button>
    </div>

    <section
      v-for="p in SUPPORTED_COOKIE_PLATFORMS"
      :key="p"
      class="section-card"
    >
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">{{ PLATFORM_LABELS[p] }}</h2>
        <span
          v-if="rows[p]?.cookie"
          class="tag bg-green-100 text-green-700"
        >已配置</span>
        <span v-else class="tag bg-gray-100 text-gray-500">未配置</span>
      </div>

      <textarea
        v-model="rows[p].cookie"
        class="input font-mono text-xs h-20 resize-y"
        placeholder="name=value; name=value; ..."
      />

      <div class="flex items-center gap-2">
        <button class="btn-primary" :disabled="rows[p]?.busy" @click="syncFromBrowser(p)">
          {{ rows[p]?.busy ? '处理中…' : '从浏览器同步' }}
        </button>
        <button class="btn-secondary" :disabled="rows[p]?.busy" @click="saveManual(p)">
          手动保存
        </button>
        <span
          v-if="rows[p]?.status?.text"
          class="text-xs"
          :class="{
            'text-green-700': rows[p].status.kind === 'ok',
            'text-red-600': rows[p].status.kind === 'err',
            'text-gray-500': rows[p].status.kind === 'idle',
          }"
        >{{ rows[p].status.text }}</span>
      </div>
    </section>
  </div>
</template>
