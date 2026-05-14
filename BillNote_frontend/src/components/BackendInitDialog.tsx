import { useMemo, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Loader2, AlertTriangle, RotateCcw, Clipboard } from 'lucide-react'
import { useBackendEvents } from '@/components/BackendHealth/useBackendEvents'

// 失败态预览里最多展示几行 stderr。比这还多就请用户去 copyLogs() 拷出来。
const STDERR_PREVIEW_LINES = 6

interface Props {
  /** 加载中：显示转圈对话框 */
  open: boolean
  /** 启动失败：显示错误 + 重启/复制日志按钮 */
  failed?: boolean
  /** 失败原因（来自 useCheckBackend.lastError 或 Tauri 事件 payload） */
  lastError?: string | null
  /** 重新走一遍 useCheckBackend 的轮询（不重启 sidecar） */
  onRetry?: () => void
}

// 加载中 + 启动失败两个状态合并在一个 dialog 里。
// 失败态比加载态更紧急：用户能看到具体原因 + 一键重启 + 一键复制日志去 issue，
// 而不是面对一个永远转圈的对话框。
function BackendInitDialog({ open, failed = false, lastError = null, onRetry }: Props) {
  const { isTauri, restart, copyLogs, logs } = useBackendEvents()
  const [restarting, setRestarting] = useState(false)
  const [copyResult, setCopyResult] = useState<'idle' | 'ok' | 'fail'>('idle')

  // 从 ring buffer 里挑最后几行 stderr —— 它们比 lastError（hook 自己总结的那句）信息密度更高，
  // 通常 Python traceback 的最后一行就是真正的错误类型 + 消息
  const stderrPreview = useMemo(() => {
    if (!failed || !logs?.length) return []
    return logs
      .filter((l) => l.level === 'error')
      .slice(-STDERR_PREVIEW_LINES)
      .map((l) => l.text)
  }, [failed, logs])

  // 任一态需要展示就保持 dialog 开着，关掉只在两个 flag 都熄灭时发生
  const isOpen = open || failed

  const handleRestart = async () => {
    setRestarting(true)
    try {
      if (isTauri) await restart()
      onRetry?.()
    } catch {
      // restart 内部已经 append 到 log，这里不再 toast
    } finally {
      setRestarting(false)
    }
  }

  const handleCopy = async () => {
    const ok = await copyLogs()
    setCopyResult(ok ? 'ok' : 'fail')
    setTimeout(() => setCopyResult('idle'), 2000)
  }

  if (failed) {
    return (
      <Dialog open={isOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="w-5 h-5" />
              后端启动失败
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2 text-sm">
            <p className="text-muted-foreground">
              {lastError || '后端在预计时间内未就绪。'}
            </p>
            {stderrPreview.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">
                  后端最近 {stderrPreview.length} 行错误日志
                  <span className="opacity-60">（完整日志请用「复制启动日志」）</span>:
                </p>
                <pre className="max-h-32 overflow-auto rounded bg-zinc-900 px-2 py-1.5 font-mono text-[11px] leading-snug text-red-200">
                  {stderrPreview.join('\n')}
                </pre>
              </div>
            )}
            <div className="text-xs text-muted-foreground space-y-1">
              <p>常见原因：</p>
              <ul className="list-disc list-inside space-y-0.5 pl-1">
                <li>安装路径含中文 / 空格（PyInstaller 在这种路径下经常起不来）</li>
                <li>没装 ffmpeg / 端口 8483 被占用</li>
                <li>首次启动时 whisper 模型下载未完成</li>
              </ul>
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                size="sm"
                onClick={handleRestart}
                disabled={restarting}
                className="gap-1.5"
              >
                {restarting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RotateCcw className="w-4 h-4" />
                )}
                {isTauri ? (restarting ? '重启中…' : '重启后端') : '重试'}
              </Button>
              {isTauri && (
                <Button size="sm" variant="outline" onClick={handleCopy} className="gap-1.5">
                  <Clipboard className="w-4 h-4" />
                  {copyResult === 'ok'
                    ? '已复制 ✓'
                    : copyResult === 'fail'
                      ? '复制失败'
                      : '复制启动日志'}
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground pt-2">
              仍然无法解决？复制日志去&nbsp;
              <a
                href="https://github.com/JefferyHcool/BiliNote/issues"
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 underline"
              >
                GitHub Issues
              </a>
              &nbsp;反馈。
            </p>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  // 默认加载态
  return (
    <Dialog open={isOpen}>
      <DialogContent className="text-center">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-center gap-2">
            <Loader2 className="animate-spin w-5 h-5" />
            后端正在初始化中…
          </DialogTitle>
        </DialogHeader>
        <p className="text-muted-foreground mt-2">
          请稍候，系统正在启动后端服务。首次启动可能需要 10-30 秒解压依赖。
        </p>
      </DialogContent>
    </Dialog>
  )
}

export default BackendInitDialog
