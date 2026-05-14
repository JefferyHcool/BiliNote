import { useEffect, useRef } from 'react'
import { useTaskStore, type TaskProgress } from '@/store/taskStore'
import { get_task_status } from '@/services/note.ts'
import toast from 'react-hot-toast'

export const useTaskPolling = (interval = 3000) => {
  const tasks = useTaskStore(state => state.tasks)
  const updateTaskContent = useTaskStore(state => state.updateTaskContent)

  const tasksRef = useRef(tasks)

  useEffect(() => {
    tasksRef.current = tasks
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
            const { markdown, transcript, audio_meta } = res.result
            toast.success('笔记生成成功')
            updateTaskContent(task.id, {
              status,
              markdown,
              transcript,
              audioMeta: audio_meta,
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
