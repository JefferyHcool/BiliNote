import { useEffect, useState } from 'react'

// 桌面端启动诊断横幅。监听 Tauri 侧 emit 的 backend-warning / backend-error / backend-terminated。
// 只在 Tauri 环境生效；纯 web 环境（无 window.__TAURI_INTERNALS__）下静默不挂载。

type Severity = 'info' | 'warning' | 'error'

interface DiagnosticPayload {
  exe_path?: string
  path_has_non_ascii?: boolean
  path_has_space?: boolean
  parent_writable?: boolean
  platform?: string
}

interface BannerState {
  severity: Severity
  title: string
  detail: string
  payload?: DiagnosticPayload
  dismissible: boolean
}

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

function describeWarning(payload: DiagnosticPayload): { title: string; detail: string } {
  const parts: string[] = []
  if (payload.path_has_non_ascii) {
    parts.push('安装路径包含非 ASCII 字符（中文 / 日文等）')
  }
  if (payload.path_has_space) {
    parts.push('安装路径包含空格')
  }
  if (payload.parent_writable === false) {
    parts.push('安装目录不可写（缺少权限或只读）')
  }
  return {
    title: '检测到可能导致后端启动失败的安装路径',
    detail:
      `${parts.join('；')}。\n` +
      '建议把 BiliNote 重新安装到一个纯英文、无空格、可写的路径下（如 C:\\BiliNote\\ 或 /Applications/）。\n' +
      `当前路径：${payload.exe_path || '未知'}`,
  }
}

const StartupBanner = () => {
  const [banner, setBanner] = useState<BannerState | null>(null)

  useEffect(() => {
    if (!isTauri) return

    let unlisteners: Array<() => void> = []

    ;(async () => {
      const { listen } = await import('@tauri-apps/api/event')

      const offWarning = await listen<DiagnosticPayload>('backend-warning', event => {
        const { title, detail } = describeWarning(event.payload || {})
        setBanner({
          severity: 'warning',
          title,
          detail,
          payload: event.payload,
          dismissible: true,
        })
      })

      const offTerminated = await listen<number | null>('backend-terminated', event => {
        setBanner({
          severity: 'error',
          title: '后端进程已退出',
          detail: `退出码：${event.payload ?? '未知'}。打开「部署监控」或重启应用以恢复。`,
          dismissible: false,
        })
      })

      // backend-error 是 sidecar stderr，量大噪音多，这里不直接展示，留给 P2 的日志面板。
      unlisteners = [offWarning, offTerminated]
    })()

    return () => {
      unlisteners.forEach(fn => fn())
    }
  }, [])

  if (!banner) return null

  const colorByLevel: Record<Severity, string> = {
    info: 'bg-blue-50 border-blue-300 text-blue-900',
    warning: 'bg-amber-50 border-amber-300 text-amber-900',
    error: 'bg-red-50 border-red-300 text-red-900',
  }

  const iconByLevel: Record<Severity, string> = {
    info: 'ℹ️',
    warning: '⚠️',
    error: '✕',
  }

  return (
    <div
      className={`fixed left-0 right-0 top-0 z-[9999] flex items-start gap-3 border-b px-4 py-2 text-sm shadow-sm ${colorByLevel[banner.severity]}`}
    >
      <span className="text-lg">{iconByLevel[banner.severity]}</span>
      <div className="flex-1 min-w-0">
        <div className="font-medium">{banner.title}</div>
        <pre className="mt-0.5 whitespace-pre-wrap break-words font-sans text-xs opacity-90">
          {banner.detail}
        </pre>
      </div>
      {banner.dismissible && (
        <button
          className="shrink-0 rounded px-2 py-0.5 text-xs hover:bg-black/10"
          onClick={() => setBanner(null)}
        >
          知道了
        </button>
      )}
    </div>
  )
}

export default StartupBanner
