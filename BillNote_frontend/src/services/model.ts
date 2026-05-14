import request from '@/utils/request.ts'

// opts.silent: 让本次请求失败时不弹全局红 toast（调用方自行 catch 处理，
// 比如 onboarding 撞名重试这种预期内失败）
interface CallOpts { silent?: boolean }
const cfg = (o?: CallOpts) => (o?.silent ? { suppressToast: true } : undefined)

export const getProviderList = async (opts?: CallOpts) => {
  return await request.get('/get_all_providers', cfg(opts))
}
export const getProviderById = async (id: string) => {
  return await request.get(`/get_provider_by_id/${id}`)
}
export const updateProviderById = async (data: any, opts?: CallOpts) => {
  return await request.post('/update_provider', data, cfg(opts))
}

export const addProvider = async (data: any, opts?: CallOpts) => {
  return await request.post('/add_provider', data, cfg(opts))
}

export const testConnection = async (data: any, opts?: CallOpts) => {
  return await request.post('/connect_test', data, cfg(opts))
}

export const fetchModels = async (providerId: string) => {
  return await request.get('/model_list/' + providerId)
}

export const fetchEnableModelById = async (id: string) => {
  return await request.get('/model_enable/' + id)
}

export async function addModel(
  data: { provider_id: string; model_name: string },
  opts?: CallOpts,
) {
  return request.post('/models', data, cfg(opts))
}

export const fetchEnableModels = async () => {
  return await request.get('/model_list')
}

export const deleteModelById = async (modelId: number) => {
  return await request.get(`/models/delete/${modelId}`)
}