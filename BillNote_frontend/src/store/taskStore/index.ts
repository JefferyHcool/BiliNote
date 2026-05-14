import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { delete_task, generateNote } from '@/services/note.ts'
import { v4 as uuidv4 } from 'uuid'
import toast from 'react-hot-toast'
import { get, set, del } from 'idb-keyval'


export type TaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'ANALYZING_VIDEO'
  | 'SUMMARIZING'
  | 'SAVING'

export interface TaskProgress {
  progress: number
  elapsed_time: number
  phase_durations: Record<string, number>
  phase_started_at?: string
  started_at?: string
}

export interface AudioMeta {
  cover_url: string
  duration: number
  file_path: string
  platform: string
  raw_info: any
  title: string
  video_id: string
}

export interface Segment {
  start: number
  end: number
  text: string
}

export interface Transcript {
  full_text: string
  language: string
  raw: any
  segments: Segment[]
}
export interface Markdown {
  ver_id: string
  content: string
  style: string
  model_name: string
  created_at: string
}

export interface Task {
  id: string
  markdown: string|Markdown [] //为了兼容之前的笔记
  transcript: Transcript
  status: TaskStatus
  audioMeta: AudioMeta
  createdAt: string
  taskProgress?: TaskProgress
  formData?: {
    video_url?: string
    link?: boolean
    screenshot?: boolean
    platform?: string
    quality?: string
    model_name?: string
    provider_id?: string
    style?: string
    [key: string]: any
  }
}

interface TaskStore {
  tasks: Task[]
  currentTaskId: string | null
  addPendingTask: (taskId: string, platform: string, formData?: any) => void
  updateTaskContent: (id: string, data: Partial<Omit<Task, 'id' | 'createdAt'>>) => void
  removeTask: (id: string) => void
  clearTasks: () => void
  setCurrentTask: (taskId: string | null) => void
  getCurrentTask: () => Task | null
  retryTask: (id: string) => void
}

export const useTaskStore = create<TaskStore>()(
  persist(
    (set, get) => ({
      tasks: [],
      currentTaskId: null,

      addPendingTask: (taskId: string, platform: string, formData: any) =>

        set(state => ({
          tasks: [
            {
              formData: formData,
              id: taskId,
              status: 'PENDING',
              markdown: '',
              platform: platform,
              transcript: {
                full_text: '',
                language: '',
                raw: null,
                segments: [],
              },
              createdAt: new Date().toISOString(),
              audioMeta: {
                cover_url: '',
                duration: 0,
                file_path: '',
                platform: '',
                raw_info: null,
                title: '',
                video_id: '',
              },
            },
            ...state.tasks,
          ],
          currentTaskId: taskId, // 默认设置为当前任务
        })),

      updateTaskContent: (id, data) =>
          set(state => ({
            tasks: state.tasks.map(task => {
              if (task.id !== id) return task

              if (task.status === 'SUCCESS' && data.status === 'SUCCESS' && !data.markdown) return task

              // 如果是 markdown 字符串，封装为版本
              if (typeof data.markdown === 'string') {
                const prev = task.markdown
                const nextFormData = {
                  ...task.formData,
                  ...data.formData,
                }
                const currentContent = Array.isArray(prev) ? prev[0]?.content : prev
                if (currentContent === data.markdown) {
                  return {
                    ...task,
                    ...data,
                    formData: nextFormData,
                    markdown: prev,
                  }
                }

                const newVersion: Markdown = {
                  ver_id: `${task.id}-${uuidv4()}`,
                  content: data.markdown,
                  style: nextFormData?.style || '',
                  model_name: nextFormData?.model_name || '',
                  created_at: new Date().toISOString(),
                }

                let updatedMarkdown: Markdown[]
                if (Array.isArray(prev)) {
                  updatedMarkdown = [newVersion, ...prev]
                } else {
                  updatedMarkdown = [
                    newVersion,
                    ...(typeof prev === 'string' && prev
                        ? [{
                          ver_id: `${task.id}-${uuidv4()}`,
                          content: prev,
                          style: nextFormData?.style || '',
                          model_name: nextFormData?.model_name || '',
                          created_at: new Date().toISOString(),
                        }]
                        : []),
                  ]
                }

                return {
                  ...task,
                  ...data,
                  formData: nextFormData,
                  markdown: updatedMarkdown,
                }
              }

              return { ...task, ...data }
            }),
          })),


      getCurrentTask: () => {
        const currentTaskId = get().currentTaskId
        return get().tasks.find(task => task.id === currentTaskId) || null
      },
      retryTask: async (id: string, payload?: any) => {

        if (!id){
          toast.error('任务不存在')
          return
        }
        const task = get().tasks.find(task => task.id === id)
        console.log('retry',task)
        if (!task) return

        const newFormData = payload || task.formData
        await generateNote({
          ...newFormData,
          task_id: id,
        })

        set(state => ({
          tasks: state.tasks.map(t =>
              t.id === id
                  ? {
                    ...t,
                    formData: newFormData, // ✅ 显式更新 formData
                    status: 'PENDING',
                  }
                  : t
          ),
        }))
      },


      removeTask: async id => {
        const task = get().tasks.find(t => t.id === id)
        if (task) {
          try {
            await delete_task({
              task_id: task.id,
              video_id: task.audioMeta.video_id,
              platform: task.audioMeta.platform,
            })
          } catch {
            // delete_task 内部已 toast.error，这里只需阻止后续删除
            return
          }
        }
        set(state => ({
          tasks: state.tasks.filter(t => t.id !== id),
          currentTaskId: state.currentTaskId === id ? null : state.currentTaskId,
        }))
      },

      clearTasks: () => set({ tasks: [], currentTaskId: null }),

      setCurrentTask: taskId => set({ currentTaskId: taskId }),
    }),
    {
      name: 'task-storage',
      storage: createJSONStorage(() => ({
        getItem: async (name: string): Promise<string | null> => {
          const value = await get(name)
          return value ?? null
        },
        setItem: async (name: string, value: string): Promise<void> => {
          await set(name, value)
        },
        removeItem: async (name: string): Promise<void> => {
          await del(name)
        },
      })),
    }
  )
)
