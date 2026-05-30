import type React from 'react'
import { FormEvent, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getAuthStatus, login, setAuthToken } from '@/services/auth'

type AuthState = 'checking' | 'disabled' | 'authenticated' | 'login'

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>('checking')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const check = async () => {
    try {
      const status = await getAuthStatus()
      if (!status.enabled) {
        setState('disabled')
      } else if (status.authenticated) {
        setState('authenticated')
      } else {
        setAuthToken('')
        setState('login')
      }
    } catch {
      setState('login')
    }
  }

  useEffect(() => {
    check()
    const onExpired = () => {
      setAuthToken('')
      setState('login')
    }
    window.addEventListener('bilinote-auth-expired', onExpired)
    return () => window.removeEventListener('bilinote-auth-expired', onExpired)
  }, [])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(password)
      setPassword('')
      setState('authenticated')
    } catch (err: any) {
      setError(err?.msg || '登录失败，请检查访问密码')
    } finally {
      setSubmitting(false)
    }
  }

  if (state === 'checking') {
    return <div className="flex h-screen items-center justify-center text-sm text-neutral-500">检查访问权限…</div>
  }

  if (state === 'login') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4">
        <form
          onSubmit={onSubmit}
          className="w-full max-w-sm rounded-xl border bg-white p-6 shadow-sm"
        >
          <div className="mb-5 text-center">
            <div className="text-2xl font-bold text-neutral-900">BiliNote</div>
            <p className="mt-2 text-sm text-neutral-500">此自托管实例已开启访问密码</p>
          </div>
          <label className="mb-2 block text-sm font-medium text-neutral-700">访问密码</label>
          <Input
            autoFocus
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="请输入 BILINOTE_AUTH_PASSWORD"
          />
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={submitting || !password} className="mt-4 w-full">
            {submitting ? '登录中…' : '登录'}
          </Button>
          <p className="mt-4 text-xs text-neutral-400">
            用于自托管单用户访问保护；登录后同一后端的笔记历史会跨设备同步。
          </p>
        </form>
      </div>
    )
  }

  return <>{children}</>
}
