<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  addModel,
  addProvider,
  connectTest,
  deleteModel,
  getProviderById,
  getProviders,
  listAllModels,
  updateProvider,
} from '~/logic/api'
import type { Model, Provider, ProviderUpdatePayload } from '~/logic/types'

const providers = ref<Provider[]>([])
const selectedId = ref<string>('')
const editing = ref<Partial<Provider> & { api_key?: string, base_url?: string }>({})
const models = ref<Model[]>([])
const newModelName = ref('')
const isCreating = ref(false)
const message = ref<{ kind: 'ok' | 'err' | 'idle', text: string }>({ kind: 'idle', text: '' })

const isBuiltIn = computed(() => editing.value?.type === 'built-in')

async function refresh() {
  try {
    providers.value = await getProviders()
  }
  catch (e) {
    message.value = { kind: 'err', text: `加载供应商失败：${(e as Error).message}` }
  }
}

async function select(id: string) {
  isCreating.value = false
  selectedId.value = id
  message.value = { kind: 'idle', text: '' }
  try {
    const p = await getProviderById(id)
    editing.value = { ...p }
    models.value = await listAllModels(id)
  }
  catch (e) {
    message.value = { kind: 'err', text: `读取供应商失败：${(e as Error).message}` }
  }
}

function startCreate() {
  isCreating.value = true
  selectedId.value = ''
  editing.value = {
    name: '',
    api_key: '',
    base_url: '',
    type: 'custom',
    enabled: 1,
  }
  models.value = []
}

async function save() {
  message.value = { kind: 'idle', text: '保存中…' }
  try {
    if (isCreating.value) {
      const id = await addProvider({
        name: editing.value.name || '',
        api_key: editing.value.api_key || '',
        base_url: editing.value.base_url || '',
        type: 'custom',
      })
      await refresh()
      message.value = { kind: 'ok', text: '已创建' }
      if (id)
        await select(id as unknown as string)
    }
    else if (selectedId.value) {
      const payload: ProviderUpdatePayload = {
        id: selectedId.value,
        name: editing.value.name,
        api_key: editing.value.api_key,
        base_url: editing.value.base_url,
        enabled: editing.value.enabled,
      }
      await updateProvider(payload)
      await refresh()
      message.value = { kind: 'ok', text: '已保存' }
    }
  }
  catch (e) {
    message.value = { kind: 'err', text: `保存失败：${(e as Error).message}` }
  }
}

async function toggleEnabled(p: Provider) {
  try {
    await updateProvider({ id: p.id, enabled: p.enabled === 1 ? 0 : 1 })
    await refresh()
  }
  catch (e) {
    message.value = { kind: 'err', text: `切换启用失败：${(e as Error).message}` }
  }
}

async function test() {
  if (!selectedId.value)
    return
  message.value = { kind: 'idle', text: '测试中…' }
  try {
    await connectTest(selectedId.value)
    message.value = { kind: 'ok', text: '连接成功 ✓' }
  }
  catch (e) {
    message.value = { kind: 'err', text: `连接失败：${(e as Error).message}` }
  }
}

async function addNewModel() {
  if (!selectedId.value || !newModelName.value.trim())
    return
  try {
    await addModel(selectedId.value, newModelName.value.trim())
    newModelName.value = ''
    models.value = await listAllModels(selectedId.value)
  }
  catch (e) {
    message.value = { kind: 'err', text: `添加模型失败：${(e as Error).message}` }
  }
}

async function removeModel(modelId: number | string) {
  if (!confirm('确认删除该模型？'))
    return
  try {
    await deleteModel(modelId)
    if (selectedId.value)
      models.value = await listAllModels(selectedId.value)
  }
  catch (e) {
    message.value = { kind: 'err', text: `删除模型失败：${(e as Error).message}` }
  }
}

onMounted(refresh)
</script>

<template>
  <div class="p-6 flex gap-6">
    <aside class="w-64 shrink-0 flex flex-col gap-2">
      <div class="flex justify-between items-center">
        <h1 class="text-xl font-bold">模型供应商</h1>
        <button class="btn-secondary" @click="startCreate">新增</button>
      </div>
      <div class="bg-white border rounded">
        <div
          v-for="p in providers"
          :key="p.id"
          class="flex items-center justify-between gap-2 px-3 py-2 border-b last:border-b-0 cursor-pointer hover:bg-gray-50"
          :class="{ 'bg-blue-50': p.id === selectedId }"
          @click="select(p.id)"
        >
          <div class="flex items-center gap-2 min-w-0">
            <div class="truncate">{{ p.name }}</div>
            <span
              class="tag"
              :class="p.type === 'built-in' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'"
            >{{ p.type === 'built-in' ? '内置' : '自定义' }}</span>
          </div>
          <button
            class="text-xs"
            :class="p.enabled === 1 ? 'text-green-600' : 'text-gray-400'"
            :title="p.enabled === 1 ? '已启用，点击禁用' : '已禁用，点击启用'"
            @click.stop="toggleEnabled(p)"
          >
            {{ p.enabled === 1 ? '✓ 启用' : '○ 禁用' }}
          </button>
        </div>
      </div>
    </aside>

    <main class="flex-1 max-w-2xl">
      <div v-if="!selectedId && !isCreating" class="text-gray-400 text-sm pt-12 text-center">
        左侧选一个供应商查看 / 编辑，或点「新增」添加新供应商
      </div>
      <div v-else class="flex flex-col gap-4">
        <h2 class="text-lg font-semibold">
          {{ isCreating ? '新增供应商' : '编辑供应商' }}
        </h2>

        <section class="section-card">
          <label class="flex items-center gap-3 text-sm">
            <span class="w-20 text-right text-gray-600">名称</span>
            <input v-model="editing.name" class="input flex-1" :disabled="isBuiltIn">
          </label>
          <label class="flex items-center gap-3 text-sm">
            <span class="w-20 text-right text-gray-600">API Key</span>
            <input v-model="editing.api_key" class="input flex-1" type="password">
          </label>
          <label class="flex items-center gap-3 text-sm">
            <span class="w-20 text-right text-gray-600">API 地址</span>
            <input v-model="editing.base_url" class="input flex-1">
          </label>
          <label v-if="!isCreating" class="flex items-center gap-3 text-sm">
            <span class="w-20 text-right text-gray-600">类型</span>
            <input :value="editing.type" class="input flex-1" disabled>
          </label>

          <div class="flex items-center gap-2 pt-2">
            <button class="btn-primary" @click="save">{{ isCreating ? '创建' : '保存' }}</button>
            <button v-if="!isCreating" class="btn-secondary" @click="test">测试连接</button>
            <span
              v-if="message.text"
              class="text-xs"
              :class="{
                'text-green-700': message.kind === 'ok',
                'text-red-600': message.kind === 'err',
                'text-gray-500': message.kind === 'idle',
              }"
            >{{ message.text }}</span>
          </div>
        </section>

        <section v-if="!isCreating" class="section-card">
          <h3 class="font-semibold">模型列表</h3>
          <div class="flex gap-2">
            <input v-model="newModelName" class="input flex-1" placeholder="例如 gpt-4o-mini">
            <button class="btn-secondary" @click="addNewModel">添加模型</button>
          </div>
          <ul class="flex flex-col gap-1">
            <li v-for="m in models" :key="m.id" class="flex justify-between items-center px-2 py-1 rounded hover:bg-gray-50">
              <span class="text-sm">{{ m.model_name }}</span>
              <button class="text-xs text-red-500 hover:text-red-700" @click="removeModel(m.id)">删除</button>
            </li>
            <li v-if="models.length === 0" class="text-xs text-gray-400">该供应商下还没有模型</li>
          </ul>
        </section>
      </div>
    </main>
  </div>
</template>
