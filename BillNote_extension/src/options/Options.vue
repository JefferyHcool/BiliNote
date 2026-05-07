<script setup lang="ts">
import { computed, ref } from 'vue'
import GeneralPage from './pages/General.vue'
import ProvidersPage from './pages/Providers.vue'
import TranscriberPage from './pages/Transcriber.vue'
import DownloaderPage from './pages/Downloader.vue'
import MonitorPage from './pages/Monitor.vue'

const TABS = [
  { id: 'general', label: '通用', icon: '⚙️', component: GeneralPage },
  { id: 'providers', label: '模型供应商', icon: '🧠', component: ProvidersPage },
  { id: 'transcriber', label: '音频转写配置', icon: '🎙️', component: TranscriberPage },
  { id: 'downloader', label: '下载配置', icon: '🍪', component: DownloaderPage },
  { id: 'monitor', label: '部署监控', icon: '📊', component: MonitorPage },
] as const

const activeTab = ref<typeof TABS[number]['id']>('general')
const ActiveComponent = computed(() => TABS.find(t => t.id === activeTab.value)?.component ?? GeneralPage)
</script>

<template>
  <div class="flex h-screen bg-gray-50 text-gray-800">
    <aside class="w-56 shrink-0 border-r bg-white flex flex-col">
      <div class="px-4 py-4 border-b">
        <div class="text-lg font-bold">BiliNote</div>
        <div class="text-xs text-gray-500">浏览器插件设置</div>
      </div>
      <nav class="flex-1 overflow-auto py-2">
        <button
          v-for="tab in TABS"
          :key="tab.id"
          class="w-full text-left px-4 py-2 text-sm flex items-center gap-2 hover:bg-gray-100"
          :class="activeTab === tab.id ? 'bg-blue-50 text-blue-700 font-medium border-l-2 border-blue-500' : 'text-gray-700'"
          @click="activeTab = tab.id"
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </nav>
      <div class="px-4 py-2 text-xs text-gray-400 border-t">
        v0.1.0
      </div>
    </aside>

    <main class="flex-1 overflow-auto">
      <component :is="ActiveComponent" />
    </main>
  </div>
</template>

<style>
.btn-primary { @apply bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm; }
.btn-secondary { @apply bg-gray-100 text-gray-700 px-3 py-1 rounded hover:bg-gray-200 text-sm disabled:opacity-50; }
.btn-danger { @apply bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600 text-sm disabled:opacity-50; }
.tag { @apply text-xs px-1.5 py-0.5 rounded; }
.input { @apply border rounded px-2 py-1 text-sm; }
.section-card { @apply bg-white border rounded p-4 mb-4 flex flex-col gap-3; }
</style>
