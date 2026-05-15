import { FC, useEffect, useState } from 'react'
import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import type { TaskProgress } from '@/store/taskStore'

interface GenerationProgressProps {
  taskStatus: string
  taskProgress?: TaskProgress
}

const PHASES = [
  { key: 'PARSING',         label: '解析链接',  desc: '识别平台与视频 ID' },
  { key: 'DOWNLOADING',     label: '下载媒体',  desc: '获取音频 / 视频文件' },
  { key: 'TRANSCRIBING',    label: '语音转写',  desc: '将音频转换为文字' },
  { key: 'ANALYZING_VIDEO', label: '视频分析',  desc: '理解视觉内容' },
  { key: 'SUMMARIZING',     label: '生成笔记',  desc: 'LLM 整理结构化笔记' },
  { key: 'SAVING',          label: '保存任务',  desc: '写入数据库' },
]

function parseIsoMs(iso?: string): number | null {
  if (!iso) return null
  const ms = new Date(iso).getTime()
  return isNaN(ms) ? null : ms
}

function fmtSecs(s: number): string {
  if (s < 0) return '0s'
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  return `${m}m ${(s % 60).toFixed(0)}s`
}

const GenerationProgress: FC<GenerationProgressProps> = ({ taskStatus, taskProgress }) => {
  const [nowMs, setNowMs] = useState(Date.now())

  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const currentIndex = PHASES.findIndex(p => p.key === taskStatus)
  const progress = taskProgress?.progress ?? 0

  const startedMs = parseIsoMs(taskProgress?.started_at)
  const phaseStartedMs = parseIsoMs(taskProgress?.phase_started_at)

  // 使用服务器时间戳 + 本地时钟实现平滑更新，避免依赖每次轮询
  const totalElapsed = startedMs != null
    ? Math.max(0, (nowMs - startedMs) / 1000)
    : (taskProgress?.elapsed_time ?? 0)

  const phaseElapsed = phaseStartedMs != null
    ? Math.max(0, (nowMs - phaseStartedMs) / 1000)
    : 0

  return (
    <div className="w-full max-w-sm space-y-5">
      {/* 整体进度条 */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-gray-500">
          <span className="font-semibold text-primary">{progress}%</span>
          <span className="tabular-nums">⏱ {fmtSecs(totalElapsed)}</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* 排队中提示 */}
      {currentIndex === -1 && (
        <p className="text-center text-xs text-gray-400">任务排队中，等待执行…</p>
      )}

      {/* 阶段列表 */}
      <div className="space-y-2">
        {PHASES.map((phase, idx) => {
          const isDone = idx < currentIndex
          const isCurrent = idx === currentIndex
          const isPending = idx > currentIndex && currentIndex !== -1
          const duration = taskProgress?.phase_durations?.[phase.key]

          return (
            <div
              key={phase.key}
              className={`flex items-center gap-3 text-sm transition-opacity duration-300 ${
                isPending ? 'opacity-30' : ''
              }`}
            >
              {/* 状态图标 */}
              <div className="h-4 w-4 shrink-0">
                {isDone ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : isCurrent ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : (
                  <Circle className="h-4 w-4 text-gray-300" />
                )}
              </div>

              {/* 阶段名 + 描述 */}
              <div className="min-w-0 flex-1">
                <span
                  className={
                    isCurrent
                      ? 'font-semibold text-primary'
                      : isDone
                      ? 'text-gray-700'
                      : 'text-gray-400'
                  }
                >
                  {phase.label}
                </span>
                {isCurrent && (
                  <span className="ml-1.5 text-xs text-gray-400">{phase.desc}</span>
                )}
              </div>

              {/* 耗时 */}
              <span className="w-14 text-right font-mono text-xs text-gray-400 tabular-nums">
                {isDone && duration != null
                  ? fmtSecs(duration)
                  : isCurrent
                  ? `${phaseElapsed.toFixed(0)}s`
                  : ''}
              </span>
            </div>
          )
        })}
      </div>

      {/* 各阶段耗时小结（仅有已完成阶段时显示） */}
      {taskProgress?.phase_durations && Object.keys(taskProgress.phase_durations).filter(k => PHASES.some(p => p.key === k)).length > 1 && (
        <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
          <p className="mb-1.5 text-xs font-medium text-gray-500">已完成阶段</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {PHASES.filter(p => taskProgress.phase_durations[p.key] != null).map(phase => (
              <div key={phase.key} className="flex justify-between text-xs text-gray-500">
                <span>{phase.label}</span>
                <span className="font-mono tabular-nums">
                  {fmtSecs(taskProgress.phase_durations[phase.key])}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default GenerationProgress
