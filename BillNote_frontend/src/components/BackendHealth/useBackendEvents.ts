import { useEffect, useRef, useState } from 'react'

// 桌面端 Sidecar 健康度。监听 Tauri 侧的 backend-message / backend-error /
// backend-terminated / backend-restarted 事件，把 stdout/stderr 缓冲成 ring buffer，
// 同时维护进程运行状态。

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export type LogLevel = 'info' | 'error'

export interface LogEntry {
  level: LogLevel
  text: string
  ts: number
}

export type BackendStatus = 'running' | 'terminated'

const MAX_LOG_LINES = 200

interface BackendEvents {
  status: BackendStatus
  exitCode: number | null
  logs: LogEntry[]
  /** 调 Tauri 命令重启 sidecar */
  restart: () => Promise<void>
  /** 复制全部日志到剪贴板 */
  copyLogs: () => Promise<boolean>
  isTauri: boolean
}

export function useBackendEvents(): BackendEvents {
  const [status, setStatus] = useState<BackendStatus>('running')
  const [exitCode, setExitCode] = useState<number | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  // 用 ref 持有最新 logs 数组，append 时不被闭包陷阱卡到旧值
  const logsRef = useRef<LogEntry[]>([])
  // 主动重启期：Rust 在 kill 老 sidecar 前会 emit 'backend-restarting'。
  // 期间到达的 'backend-terminated' 是我们自己造成的，不要污染状态。
  const ignoreNextTerminatedRef = useRef(false)

  function append(entry: LogEntry) {
    const next = logsRef.current.concat(entry)
    if (next.length > MAX_LOG_LINES)
      next.splice(0, next.length - MAX_LOG_LINES)
    logsRef.current = next
    setLogs(next)
  }

  useEffect(() => {
    if (!isTauri) return

    let unlisteners: Array<() => void> = []

    ;(async () => {
      const { listen } = await import('@tauri-apps/api/event')

      const offMsg = await listen<string>('backend-message', event => {
        append({ level: 'info', text: stripQuotes(event.payload), ts: Date.now() })
      })
      const offErr = await listen<string>('backend-error', event => {
        append({ level: 'error', text: stripQuotes(event.payload), ts: Date.now() })
      })
      const offRestarting = await listen('backend-restarting', () => {
        // 紧接着到达的 terminated 是我们主动 kill 老 sidecar 引发的，跳过 3s
        ignoreNextTerminatedRef.current = true
        setTimeout(() => { ignoreNextTerminatedRef.current = false }, 3000)
        append({ level: 'info', text: '[Backend restarting]', ts: Date.now() })
      })
      const offTerm = await listen<number | null>('backend-terminated', event => {
        // 主动重启窗口内的 terminated 是预期副作用，仅记日志、不改状态
        if (ignoreNextTerminatedRef.current) {
          ignoreNextTerminatedRef.current = false
          append({
            level: 'info',
            text: `[Backend terminated, restart in progress] code=${event.payload ?? 'unknown'}`,
            ts: Date.now(),
          })
          return
        }
        setStatus('terminated')
        setExitCode(event.payload ?? null)
        append({
          level: 'error',
          text: `[Backend terminated] code=${event.payload ?? 'unknown'}`,
          ts: Date.now(),
        })
      })
      const offRestart = await listen('backend-restarted', () => {
        setStatus('running')
        setExitCode(null)
        append({ level: 'info', text: '[Backend restarted]', ts: Date.now() })
      })

      unlisteners = [offMsg, offErr, offRestarting, offTerm, offRestart]
    })()

    return () => {
      unlisteners.forEach(fn => fn())
    }
  }, [])

  async function restart() {
    if (!isTauri) return
    const { invoke } = await import('@tauri-apps/api/core')
    try {
      await invoke('restart_backend_sidecar')
    }
    catch (e) {
      append({ level: 'error', text: `[Restart failed] ${(e as Error).message ?? e}`, ts: Date.now() })
      throw e
    }
  }

  async function copyLogs() {
    const text = logsRef.current
      .map(l => `${new Date(l.ts).toISOString().slice(11, 19)} ${l.level === 'error' ? 'E' : 'I'} ${l.text}`)
      .join('\n')
    try {
      await navigator.clipboard.writeText(text)
      return true
    }
    catch {
      return false
    }
  }

  return { status, exitCode, logs, restart, copyLogs, isTauri }
}

// Rust 早期版本 emit 时把 stdout 包了一层 '...'，新版本已经直接 emit 原文。
// 这里做兼容：去掉外层单引号（如果有的话）。
function stripQuotes(s: string): string {
  if (typeof s !== 'string') return String(s)
  if (s.length >= 2 && s.startsWith("'") && s.endsWith("'"))
    return s.slice(1, -1)
  return s
}
