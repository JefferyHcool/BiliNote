import { useEffect, useRef, useState } from 'react'
import type { LogEntry, BackendStatus } from './useBackendEvents'

interface Props {
  status: BackendStatus
  exitCode: number | null
  logs: LogEntry[]
  health: 'green' | 'yellow' | 'red' | 'unknown'
  onRestart: () => Promise<void>
  onCopyLogs: () => Promise<boolean>
  onClose: () => void
}

const BackendLogPanel = ({ status, exitCode, logs, health, onRestart, onCopyLogs, onClose }: Props) => {
  const [restarting, setRestarting] = useState(false)
  const [copied, setCopied] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新日志进来自动滚到底
  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [logs])

  async function handleRestart() {
    setRestarting(true)
    try { await onRestart() }
    catch { /* errors already in log via useBackendEvents */ }
    finally { setRestarting(false) }
  }

  async function handleCopy() {
    const ok = await onCopyLogs()
    setCopied(ok)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <>
      {/* 半透明遮罩 */}
      <div className="fixed inset-0 z-[9998] bg-black/20" onClick={onClose} />

      <aside className="fixed right-0 bottom-0 top-0 z-[9999] flex w-[480px] max-w-[90vw] flex-col border-l bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <h2 className="text-base font-semibold">后端运行状态</h2>
            <div className="mt-0.5 text-xs text-gray-500">
              {status === 'terminated'
                ? `已退出（退出码 ${exitCode ?? 'unknown'}）`
                : health === 'red'
                  ? '运行中但无响应'
                  : health === 'yellow'
                    ? '运行中，部分系统检查未通过'
                    : '运行正常'}
            </div>
          </div>
          <button className="rounded p-1 text-gray-500 hover:bg-gray-100" onClick={onClose}>✕</button>
        </header>

        <div className="flex items-center gap-2 border-b px-4 py-2">
          <button
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            disabled={restarting}
            onClick={handleRestart}
          >
            {restarting ? '重启中…' : '重启后端'}
          </button>
          <button
            className="rounded bg-gray-100 px-3 py-1 text-sm text-gray-700 hover:bg-gray-200"
            onClick={handleCopy}
          >
            {copied ? '已复制 ✓' : '复制日志'}
          </button>
          <span className="ml-auto text-xs text-gray-400">
            最近 {logs.length} 行
          </span>
        </div>

        <div
          ref={scrollRef}
          className="flex-1 overflow-auto bg-gray-900 p-3 font-mono text-xs text-gray-100"
        >
          {logs.length === 0 ? (
            <div className="text-gray-500 italic">暂无日志输出</div>
          ) : (
            logs.map((l, i) => (
              <div
                key={`${l.ts}-${i}`}
                className={`whitespace-pre-wrap break-all leading-snug ${l.level === 'error' ? 'text-red-300' : 'text-gray-100'}`}
              >
                <span className="mr-2 text-gray-500">
                  {new Date(l.ts).toISOString().slice(11, 19)}
                </span>
                {l.text}
              </div>
            ))
          )}
        </div>

        <footer className="border-t px-4 py-2 text-xs text-gray-500">
          后端进程退出 / 无响应时，先点「重启后端」；仍不行复制日志去 issue 反馈。
        </footer>
      </aside>
    </>
  )
}

export default BackendLogPanel
