<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getDeployStatus, getSysHealth } from '~/logic/api'
import type { DeployStatus } from '~/logic/types'

const status = ref<DeployStatus | null>(null)
const health = ref<{ ok: boolean, msg?: string } | null>(null)
const loading = ref(false)
const error = ref('')

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [s, h] = await Promise.all([getDeployStatus(), getSysHealth()])
    status.value = s
    health.value = h
  }
  catch (e) {
    error.value = (e as Error).message
  }
  finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="p-6 max-w-2xl">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-xl font-bold">部署监控</h1>
      <button class="btn-secondary" :disabled="loading" @click="refresh">
        {{ loading ? '检查中…' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="text-red-600 text-sm mb-4">{{ error }}</div>

    <template v-if="status">
      <section class="section-card">
        <h2 class="font-semibold">后端</h2>
        <div class="text-sm">
          <span class="tag bg-green-100 text-green-700">{{ status.backend.status }}</span>
          <span class="ml-2 text-gray-600">端口 {{ status.backend.port }}</span>
        </div>
      </section>

      <section class="section-card">
        <h2 class="font-semibold">FFmpeg</h2>
        <div class="text-sm flex items-center gap-3">
          <span
            class="tag"
            :class="status.ffmpeg.available ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
          >{{ status.ffmpeg.available ? '可用' : '不可用' }}</span>
          <span v-if="health && !health.ok" class="text-red-600 text-xs">{{ health.msg }}</span>
        </div>
      </section>

      <section class="section-card">
        <h2 class="font-semibold">CUDA / GPU</h2>
        <div class="text-sm">
          <span
            class="tag"
            :class="status.cuda.available ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'"
          >{{ status.cuda.available ? '可用' : '不可用' }}</span>
          <div v-if="status.cuda.available" class="mt-1 text-gray-600 text-xs">
            CUDA {{ status.cuda.version }} · {{ status.cuda.gpu_name }}
          </div>
        </div>
      </section>

      <section class="section-card">
        <h2 class="font-semibold">Whisper</h2>
        <div class="text-sm text-gray-600">
          引擎：<span class="text-gray-800">{{ status.whisper.transcriber_type }}</span>
          <span v-if="status.whisper.model_size" class="ml-3">
            模型：<span class="text-gray-800">{{ status.whisper.model_size }}</span>
          </span>
        </div>
      </section>
    </template>
  </div>
</template>
