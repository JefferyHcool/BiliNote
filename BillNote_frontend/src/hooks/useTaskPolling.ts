import { useEffect, useRef } from 'react'
import { useTaskStore, type TaskProgress } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)

  const tasksRef = useRef(tasks)
  // 记录每个任务提交时间，用于跳过旧一轮的 SUCCESS 响应
  const taskSubmitTimeRef = useRef<Record<string, number>>({})

  useEffect(() => {
    tasksRef.current = tasks
    // 任务变为 PENDING 时记录时间戳
    tasks.forEach(t => {
      if (t.status === 'PENDING' && !taskSubmitTimeRef.current[t.id]) {
        taskSubmitTimeRef.current[t.id] = Date.now()
      }
      if (t.status === 'SUCCESS' || t.status === 'FAILED') {
        delete taskSubmitTimeRef.current[t.id]
      }
    })
  }, [tasks])

  useEffect(() => {
    const timer = setInterval(async () => {
      const pendingTasks = tasksRef.current.filter(
        task => task.status !== 'SUCCESS' && task.status !== 'FAILED'
      )

      if (pendingTasks.length === 0) return

      for (const task of pendingTasks) {
        try {
          const res = await get_task_status(task.id) as any
          const { status } = res

          if (!status) continue

          const taskProgress: TaskProgress = {
            progress: res.progress ?? 0,
            elapsed_time: res.elapsed_time ?? 0,
            phase_durations: res.phase_durations ?? {},
            phase_started_at: res.phase_started_at,
            started_at: res.started_at,
          }

          if (status === 'SUCCESS') {
            // 跳过旧一轮的 SUCCESS：backend 的 started_at 早于本轮提交时间说明还没刷新
            const backendStartedAt = res.started_at ? new Date(res.started_at).getTime() : 0
            const localSubmitTime = taskSubmitTimeRef.current[task.id] ?? 0
            if (localSubmitTime > 0 && backendStartedAt < localSubmitTime - 5000) {
              // 旧结果，等 backend 开始新一轮再处理
              continue
            }

            const { markdown, transcript, audio_meta, markdown_versions } = res.result
            toast.success('笔记生成成功', { id: `success-${task.id}` })
            updateTaskContent(task.id, {
              status,
              // 优先用多版本数组，无则回退到字符串
              markdown: Array.isArray(markdown_versions) && markdown_versions.length > 0
                ? markdown_versions
                : markdown,
              transcript,
              ...(audio_meta ? { audioMeta: audio_meta } : {}),
              taskProgress: { ...taskProgress, progress: 100 },
            })
          } else if (status === 'FAILED') {
            updateTaskContent(task.id, { status })
            console.warn(`⚠️ 任务 ${task.id} 失败`)
          } else {
            updateTaskContent(task.id, { status, taskProgress })
          }
        } catch (e) {
          console.error('❌ 任务轮询失败：', e)
          updateTaskContent(task.id, { status: 'FAILED' })
        }
      }
    }, interval)

    return () => clearInterval(timer)
  }, [interval])
}
