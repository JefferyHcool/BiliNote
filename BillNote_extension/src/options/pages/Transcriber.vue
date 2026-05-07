<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  downloadTranscriberModel,
  getTranscriberConfig,
  getTranscriberModelsStatus,
  setTranscriberConfig,
} from '~/logic/api'
import type {
  TranscriberConfig,
  TranscriberModelsStatus,
  TranscriberType,
  WhisperModelSize,
  WhisperModelStatus,
} from '~/logic/types'

const config = ref<TranscriberConfig | null>(null)
const status = ref<TranscriberModelsStatus | null>(null)

const selType = ref<TranscriberType>('fast-whisper')
const selSize = ref<WhisperModelSize>('medium')

const loading = ref(false)
const saving = ref(false)
const message = ref<{ kind: 'ok' | 'err' | 'idle', text: string }>({ kind: 'idle', text: '' })

const isWhisperLike = computed(() => selType.value === 'fast-whisper' || selType.value === 'mlx-whisper')

async function refresh() {
  loading.value = true
  message.value = { kind: 'idle', text: '' }
  try {
    const [cfg, st] = await Promise.all([getTranscriberConfig(), getTranscriberModelsStatus()])
    config.value = cfg
    status.value = st
    selType.value = cfg.transcriber_type
    if (cfg.whisper_model_size)
      selSize.value = cfg.whisper_model_size
  }
  catch (e) {
    message.value = { kind: 'err', text: `读取失败：${(e as Error).message}` }
  }
  finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  message.value = { kind: 'idle', text: '保存中…' }
  try {
    const cfg = await setTranscriberConfig(selType.value, isWhisperLike.value ? selSize.value : undefined)
    config.value = cfg
    message.value = { kind: 'ok', text: '已保存。下一次生成笔记会用新配置。' }
  }
  catch (e) {
    message.value = { kind: 'err', text: `保存失败：${(e as Error).message}` }
  }
  finally {
    saving.value = false
  }
}

async function triggerDownload(size: WhisperModelSize) {
  try {
    await downloadTranscriberModel(size, selType.value === 'mlx-whisper' ? 'mlx-whisper' : 'fast-whisper')
    message.value = { kind: 'ok', text: `已开始下载 ${size}` }
    await refresh()
  }
  catch (e) {
    message.value = { kind: 'err', text: `触发下载失败：${(e as Error).message}` }
  }
}

const currentSizeStatus = computed<WhisperModelStatus[]>(() => {
  if (!status.value)
    return []
  return selType.value === 'mlx-whisper' ? status.value.mlx_whisper : status.value.whisper
})

onMounted(refresh)
</script>

<template>
  <div class="p-6 max-w-3xl">
    <h1 class="text-xl font-bold mb-1">音频转写配置</h1>
    <p class="text-xs text-gray-500 mb-4">
      选择把视频音频转成文字的引擎。在线引擎（Groq / 必剪 / 快手）走第三方 API，本地 Whisper 需要先下载模型。
    </p>

    <div v-if="loading" class="text-sm text-gray-500">加载中…</div>

    <template v-else-if="config">
      <section class="section-card">
        <h2 class="font-semibold">引擎</h2>
        <select v-model="selType" class="input">
          <option v-for="opt in config.available_types" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
        <p v-if="selType === 'mlx-whisper' && !config.mlx_whisper_available" class="text-xs text-red-600">
          ⚠ 当前后端没有装 mlx_whisper 包（仅 macOS 可用）。如果不是 Mac，请改用 fast-whisper / Groq / 必剪 / 快手。
        </p>
      </section>

      <section v-if="isWhisperLike" class="section-card">
        <h2 class="font-semibold">Whisper 模型大小</h2>
        <select v-model="selSize" class="input">
          <option v-for="s in config.whisper_model_sizes" :key="s" :value="s">
            {{ s }}
          </option>
        </select>

        <h3 class="text-sm font-medium mt-2">下载状态</h3>
        <table class="text-sm w-full">
          <thead>
            <tr class="text-left text-gray-500">
              <th class="py-1 font-normal">模型</th>
              <th class="py-1 font-normal">本地</th>
              <th class="py-1 font-normal">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in currentSizeStatus" :key="row.model_size" class="border-t">
              <td class="py-1">{{ row.model_size }}</td>
              <td class="py-1">
                <span v-if="row.downloaded" class="tag bg-green-100 text-green-700">已下载</span>
                <span v-else-if="row.downloading" class="tag bg-yellow-100 text-yellow-700">下载中…</span>
                <span v-else class="tag bg-gray-100 text-gray-500">未下载</span>
              </td>
              <td class="py-1">
                <button
                  v-if="!row.downloaded && !row.downloading"
                  class="btn-secondary"
                  @click="triggerDownload(row.model_size)"
                >
                  下载
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="flex items-center gap-3">
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
        <button class="btn-secondary" @click="refresh">刷新</button>
        <span
          v-if="message.text"
          class="text-xs"
          :class="{
            'text-green-700': message.kind === 'ok',
            'text-red-600': message.kind === 'err',
            'text-gray-500': message.kind === 'idle',
          }"
        >{{ message.text }}</span>
      </section>
    </template>
  </div>
</template>
