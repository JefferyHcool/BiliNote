<script setup lang="ts">
function openOptionsPage() {
  browser.runtime.openOptionsPage()
}
</script>

<template>
  <main class="w-full h-full p-4 flex flex-col gap-3 text-sm text-gray-700">
    <h1 class="text-base font-semibold">BiliNote 侧边栏</h1>
    <p class="text-gray-500">
      P3 计划：在这里展示任务进度、思维导图与 RAG 问答。
      当前 MVP 仅启用工具栏 popup。
    </p>
    <button class="bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded w-fit" @click="openOptionsPage">
      打开设置
    </button>
  </main>
</template>
