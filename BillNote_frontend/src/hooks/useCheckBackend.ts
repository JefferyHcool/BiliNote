import { useCallback, useEffect, useRef, useState } from 'react'

// 后端就绪检测的几个时间常量
// - 总等待上限 60s：超过这个时间没就绪就切「启动失败」UI，
//   不再像旧实现 while(true) 无限转
// - 轮询间隔 2s：比旧的 10s 更敏感，桌面端 sidecar 5-15s 解压期内能尽快感知就绪
// - 单次请求超时 5s，避免连接 hang 拖到下一轮
const TOTAL_TIMEOUT_MS = 60_000
const POLL_INTERVAL_MS = 2_000
const PROBE_TIMEOUT_MS = 5_000

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

// 直接用 fetch 而非 utils/request 的共享 axios：那个 axios 装了全局 toast 拦截器，
// 启动期每次 /sys_check 失败都会弹一个红色 toast，2s 一次轮询会叠出十几个。
function getBackendBase(): string {
  const fromEnv = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined
  return ((fromEnv && fromEnv.length > 0) ? fromEnv : '/api').replace(/\/$/, '')
}

async function probeSysCheck(): Promise<boolean> {
  const url = `${getBackendBase()}/sys_check`
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), PROBE_TIMEOUT_MS)
  try {
    const res = await fetch(url, { signal: ctrl.signal })
    if (!res.ok) return false
    const json = await res.json().catch(() => null)
    return json?.code === 0
  }
  catch {
    return false
  }
  finally {
    clearTimeout(t)
  }
}

interface Status {
  loading: boolean
  initialized: boolean
  failed: boolean
  lastError: string | null
}

interface BackendCheck extends Status {
  retry: () => void
}

const initialStatus: Status = {
  loading: true,
  initialized: false,
  failed: false,
  lastError: null,
}

/**
 * 后端就绪检测。
 *
 * 三路信号汇聚：
 *  1. HTTP 轮询 /sys_check —— 所有平台通用
 *  2. Tauri 'backend-ready' 事件 —— 桌面端 sidecar 探测器先于 HTTP 一步触达
 *  3. Tauri 'backend-terminated' / 'backend-startup-timeout' 事件 —— sidecar 死了或超时
 *     立即进失败态，不再继续轮询（旧实现的 while(true) 就是死在这里）
 *
 * 任何一路报「ready」即成功；任何一路报「失败」立即停掉所有轮询。
 */
export const useCheckBackend = (): BackendCheck => {
  const [status, setStatus] = useState<Status>(initialStatus)
  // tick 用来强制重启 useEffect（retry 时 +1），不引入 ref 互斥逻辑的复杂性
  const [tick, setTick] = useState(0)
  // 标记当前 effect 是否已 settle（避免后到的事件覆盖已确定的成功/失败态）
  const settledRef = useRef(false)

  const retry = useCallback(() => {
    settledRef.current = false
    setStatus(initialStatus)
    setTick((t) => t + 1)
  }, [])

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null
    let pollTimerId: ReturnType<typeof setTimeout> | null = null
    let cancelled = false
    const tauriUnsubs: Array<() => void> = []

    const markReady = () => {
      if (cancelled || settledRef.current) return
      settledRef.current = true
      setStatus({ loading: false, initialized: true, failed: false, lastError: null })
    }

    const markFailed = (msg: string) => {
      if (cancelled || settledRef.current) return
      settledRef.current = true
      setStatus({ loading: false, initialized: false, failed: true, lastError: msg })
    }

    const poll = async () => {
      if (cancelled || settledRef.current) return
      const ok = await probeSysCheck()
      if (cancelled || settledRef.current) return
      if (ok) {
        markReady()
        return
      }
      // 单次失败不报 toast、不抛错，继续轮询
      setStatus((s) => ({ ...s, lastError: '后端尚未响应' }))
      pollTimerId = setTimeout(poll, POLL_INTERVAL_MS)
    }

    // 总超时兜底
    timeoutId = setTimeout(() => {
      markFailed(`后端 ${TOTAL_TIMEOUT_MS / 1000}s 内未就绪，请检查后端日志或重启`)
    }, TOTAL_TIMEOUT_MS)

    // 桌面端订阅 Tauri 事件（动态 import 避免 web 端打包报错）
    if (isTauri) {
      import('@tauri-apps/api/event')
        .then(async ({ listen }) => {
          if (cancelled) return
          const offReady = await listen<number>('backend-ready', () => markReady())
          const offTimeout = await listen<string>('backend-startup-timeout', (e) => {
            markFailed(typeof e.payload === 'string' ? e.payload : '后端启动超时')
          })
          const offTerm = await listen<number | null>('backend-terminated', (e) => {
            const code = e.payload
            markFailed(`后端进程已退出 (code=${code ?? 'unknown'})`)
          })
          tauriUnsubs.push(offReady, offTimeout, offTerm)
        })
        .catch((err) => {
          // 拿不到 @tauri-apps/api/event 不致命，继续走 HTTP 轮询
          console.warn('[useCheckBackend] 无法订阅 Tauri 事件:', err)
        })
    }

    // 立刻开始第一轮轮询
    poll()

    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
      if (pollTimerId) clearTimeout(pollTimerId)
      tauriUnsubs.forEach((off) => {
        try {
          off()
        } catch {
          /* noop */
        }
      })
    }
  }, [tick])

  return { ...status, retry }
}
