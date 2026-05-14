import { useEffect, useState } from 'react'
import { useBackendEvents } from './useBackendEvents'
import BackendLogPanel from './BackendLogPanel'

// 健康度判定：
// - 绿：sidecar running 且 /sys_health 通
// - 黄：sidecar running 但 /sys_health 失败 (ffmpeg 缺等)
// - 红：sidecar terminated 或 /sys_health 连续 3 次失败

type Health = 'green' | 'yellow' | 'red' | 'unknown'

const HEALTH_POLL_MS = 5000
// 路径不带 /api/，因为 backendBase() 已经把它包进 baseURL 了（同 axios 实例的语义）。
// 之前写 '/api/sys_health' + base='http://host/api' = 双 /api → 一直 404。
const SYS_HEALTH_PATH = '/sys_health'

function backendBase(): string {
  // 与 utils/request.ts 的 baseURL 计算保持一致：env 没设走 '/api' 兜底。
  const fromEnv = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined
  return ((fromEnv && fromEnv.length > 0) ? fromEnv : '/api').replace(/\/$/, '')
}

const BackendHealthIndicator = () => {
  const { status, isTauri, exitCode, logs, restart, copyLogs } = useBackendEvents()
  const [open, setOpen] = useState(false)
  const [healthCheckFailures, setHealthCheckFailures] = useState(0)
  const [lastHealthOk, setLastHealthOk] = useState<boolean | null>(null)

  // 仅在 Tauri 环境挂指示器；纯 web 用户由 useCheckBackend 接管
  useEffect(() => {
    if (!isTauri) return
    let mounted = true

    async function ping() {
      try {
        const res = await fetch(`${backendBase()}${SYS_HEALTH_PATH}`)
        const ok = res.ok
        if (!mounted) return
        if (ok) {
          setHealthCheckFailures(0)
          setLastHealthOk(true)
        }
        else {
          setHealthCheckFailures(c => c + 1)
          setLastHealthOk(false)
        }
      }
      catch {
        if (!mounted) return
        setHealthCheckFailures(c => c + 1)
        setLastHealthOk(false)
      }
    }

    ping()
    const t = setInterval(ping, HEALTH_POLL_MS)
    return () => {
      mounted = false
      clearInterval(t)
    }
  }, [isTauri])

  if (!isTauri) return null

  const health: Health = (() => {
    if (status === 'terminated') return 'red'
    if (healthCheckFailures >= 3) return 'red'
    if (lastHealthOk === false) return 'yellow'
    if (lastHealthOk === true) return 'green'
    return 'unknown'
  })()

  const colorMap: Record<Health, string> = {
    green: 'bg-green-500',
    yellow: 'bg-amber-500',
    red: 'bg-red-500',
    unknown: 'bg-gray-400',
  }

  const labelMap: Record<Health, string> = {
    green: '后端运行正常',
    yellow: '后端运行中（部分检查未通过）',
    red: status === 'terminated' ? `后端已退出 (code=${exitCode ?? 'unknown'})` : '后端无响应',
    unknown: '后端状态未知',
  }

  return (
    <>
      <button
        className="fixed right-3 bottom-3 z-[9998] flex items-center gap-2 rounded-full border bg-white px-3 py-1.5 text-xs shadow hover:shadow-md"
        title={labelMap[health]}
        onClick={() => setOpen(true)}
      >
        <span className={`inline-block h-2 w-2 rounded-full ${colorMap[health]}${health === 'red' || health === 'yellow' ? ' animate-pulse' : ''}`} />
        <span className="text-gray-700">后端</span>
      </button>

      {open && (
        <BackendLogPanel
          status={status}
          exitCode={exitCode}
          logs={logs}
          health={health}
          onRestart={restart}
          onCopyLogs={copyLogs}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}

export default BackendHealthIndicator
