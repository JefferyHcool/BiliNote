<script setup lang="ts">
import { computed } from 'vue'
import type { TaskStatus } from '~/logic/types'

const props = defineProps<{ status: TaskStatus, message?: string }>()

const STAGE_ORDER: TaskStatus[] = ['PENDING', 'PARSING', 'DOWNLOADING', 'TRANSCRIBING', 'SUMMARIZING', 'FORMATTING', 'SAVING', 'SUCCESS']
const STAGE_LABELS: Record<TaskStatus, string> = {
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

const currentIdx = computed(() => STAGE_ORDER.indexOf(props.status))
const isFailed = computed(() => props.status === 'FAILED')
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center gap-2 text-sm">
      <span :class="isFailed ? 'text-red-600' : 'text-blue-600'" class="font-medium">
        {{ STAGE_LABELS[status] }}
      </span>
      <span v-if="message" class="text-gray-500 text-xs truncate">{{ message }}</span>
    </div>
    <div v-if="!isFailed" class="flex gap-1">
      <div
        v-for="(s, i) in STAGE_ORDER"
        :key="s"
        class="h-1 flex-1 rounded-full"
        :class="i <= currentIdx ? 'bg-blue-500' : 'bg-gray-200'"
      />
    </div>
    <div v-else class="h-1 rounded-full bg-red-500" />
  </div>
</template>
