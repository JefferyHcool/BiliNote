import request from '@/utils/request'

export interface ProxyConfig {
  enabled: boolean
  url: string
  /** 后端实际生效的代理（可能来自配置，也可能来自 HTTP_PROXY 环境变量兜底） */
  effective: string
}

export const getProxyConfig = async (): Promise<ProxyConfig> => {
  return await request.get('/proxy_config')
}

export const updateProxyConfig = async (data: {
  enabled: boolean
  url?: string
}): Promise<ProxyConfig> => {
  return await request.post('/proxy_config', data)
}
