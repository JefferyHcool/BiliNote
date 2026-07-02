import request from '@/utils/request'

export const AUTH_TOKEN_KEY = 'bilinote-auth-token'

export interface AuthStatus {
  enabled: boolean
  authenticated: boolean
}

export const getAuthToken = () => localStorage.getItem(AUTH_TOKEN_KEY) || ''

export const setAuthToken = (token: string) => {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
  else localStorage.removeItem(AUTH_TOKEN_KEY)
}

export const withAuthTokenQuery = (url: string) => {
  const token = getAuthToken()
  if (!token) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}access_token=${encodeURIComponent(token)}`
}

export const getAuthStatus = async (): Promise<AuthStatus> => {
  return await request.get('/auth/status', { suppressToast: true })
}

export const login = async (password: string): Promise<{ token: string; enabled: boolean }> => {
  const res = await request.post('/auth/login', { password }, { suppressToast: true })
  if (res?.token) setAuthToken(res.token)
  return res
}

export const logout = async () => {
  try {
    await request.post('/auth/logout', {}, { suppressToast: true })
  } finally {
    setAuthToken('')
  }
}
