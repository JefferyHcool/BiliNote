import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { delete_task, generateNote, type GenerateNotePayload } from '@/services/note.ts'
import { v4 as uuidv4 } from 'uuid'
import toast from 'react-hot-toast'
import { get, set, del } from 'idb-keyval'


export type TaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'DOWNLOADING'
  | 'TRANSCRIBING'
  | 'SUMMARIZING'
  | 'FORMATTING'
  | 'SAVING'
  | 'SUCCESS'
  | 'FAILED'

export type HistorySort = 'latest' | 'earliest' | 'title'

export interface NoteProject {
  id: string
  name: string
  createdAt: string
  updatedAt: string
}

export interface AudioMeta {
  cover_url: string
  duration: number
  file_path: string
  platform: string
  raw_info: unknown
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
  raw: unknown
  segments: Segment[]
}
export interface Markdown {
  ver_id: string
  content: string
  style: string
  model_name: string
  created_at: string
}

export interface TaskFormData extends GenerateNotePayload {
  batch_id?: string
  batch_page?: number
}

export interface Task {
  id: string
  platform: string
  projectId?: string | null
  markdown: string|Markdown [] //为了兼容之前的笔记
  transcript: Transcript
  status: TaskStatus
  audioMeta: AudioMeta
  createdAt: string
  lastGeneratedAt?: string
  formData: TaskFormData
}

interface TaskStore {
  tasks: Task[]
  projects: NoteProject[]
  currentTaskId: string | null
  selectedProjectId: string
  historySort: HistorySort
  addPendingTask: (taskId: string, platform: string, formData: TaskFormData, title?: string) => void
  addPendingTasks: (items: Array<{
    taskId: string
    platform: string
    formData: TaskFormData
    title?: string
  }>) => void
  updateTaskContent: (id: string, data: Partial<Omit<Task, 'id' | 'createdAt'>>) => void
  removeTask: (id: string) => void
  clearTasks: () => void
  setCurrentTask: (taskId: string | null) => void
  getCurrentTask: () => Task | null
  retryTask: (id: string, payload?: TaskFormData) => void
  createProject: (name: string) => NoteProject | null
  renameProject: (id: string, name: string) => boolean
  deleteProject: (id: string) => void
  moveTaskToProject: (taskId: string, projectId: string | null) => void
  moveTasksToProject: (taskIds: string[], projectId: string | null) => void
  setSelectedProject: (projectId: string) => void
  setHistorySort: (sort: HistorySort) => void
}

export const useTaskStore = create<TaskStore>()(
  persist(
    (set, get) => ({
      tasks: [],
      projects: [],
      currentTaskId: null,
      selectedProjectId: 'all',
      historySort: 'latest',

      addPendingTask: (taskId: string, platform: string, formData: TaskFormData, title = '') =>

        set(state => {
          const createdAt = new Date().toISOString()
          return {
            tasks: [
              {
                formData,
                id: taskId,
                status: 'PENDING',
                markdown: '',
                platform,
                projectId: null,
                transcript: {
                  full_text: '',
                  language: '',
                  raw: null,
                  segments: [],
                },
                createdAt,
                lastGeneratedAt: createdAt,
                audioMeta: {
                  cover_url: '',
                  duration: 0,
                  file_path: '',
                  platform: '',
                  raw_info: null,
                  title,
                  video_id: '',
                },
              },
              ...state.tasks,
            ],
            currentTaskId: taskId, // 默认设置为当前任务
          }
        }),

      addPendingTasks: items =>
        set(state => {
          if (items.length === 0) return state
          const createdAt = new Date().toISOString()
          const pendingTasks: Task[] = items.map(item => ({
            formData: item.formData,
            id: item.taskId,
            status: 'PENDING',
            markdown: '',
            platform: item.platform,
            projectId: null,
            transcript: {
              full_text: '',
              language: '',
              raw: null,
              segments: [],
            },
            createdAt,
            lastGeneratedAt: createdAt,
            audioMeta: {
              cover_url: '',
              duration: 0,
              file_path: '',
              platform: item.platform,
              raw_info: null,
              title: item.title || '',
              video_id: '',
            },
          }))
          return {
            tasks: [...pendingTasks, ...state.tasks],
            currentTaskId: pendingTasks[0].id,
          }
        }),

      updateTaskContent: (id, data) =>
          set(state => ({
            tasks: state.tasks.map(task => {
              if (task.id !== id) return task

              if (task.status === 'SUCCESS' && data.status === 'SUCCESS') return task
              const generationUpdate =
                data.status === 'SUCCESS'
                  ? { lastGeneratedAt: new Date().toISOString() }
                  : {}

              // 如果是 markdown 字符串，封装为版本
              if (typeof data.markdown === 'string') {
                const prev = task.markdown
                const newVersion: Markdown = {
                  ver_id: `${task.id}-${uuidv4()}`,
                  content: data.markdown,
                  style: task.formData.style || '',
                  model_name: task.formData.model_name || '',
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
                          style: task.formData.style || '',
                          model_name: task.formData.model_name || '',
                          created_at: new Date().toISOString(),
                        }]
                        : []),
                  ]
                }

                return {
                  ...task,
                  ...data,
                  ...generationUpdate,
                  markdown: updatedMarkdown,
                }
              }

              return { ...task, ...data, ...generationUpdate }
            }),
          })),


      getCurrentTask: () => {
        const currentTaskId = get().currentTaskId
        return get().tasks.find(task => task.id === currentTaskId) || null
      },
      retryTask: async (id: string, payload?: TaskFormData) => {

        if (!id){
          toast.error('任务不存在')
          return
        }
        const task = get().tasks.find(task => task.id === id)
        console.log('retry',task)
        if (!task) return

        const newFormData = payload || task.formData
        try {
          await generateNote({
            ...newFormData,
            task_id: id,
          })
        } catch (e: unknown) {
          const error = e as { data?: { reason?: string; downloading?: boolean } }
          // 就绪门禁：转写模型未下载好。不要把任务标成 PENDING（会一直转），
          // 给提示让用户先去下载。
          if (error.data?.reason === 'transcriber_model_not_ready') {
            toast.error(
              error.data.downloading
                ? '转写模型正在下载中，请稍候再重试'
                : '转写模型尚未下载，请先去「设置 → 音频转写配置」页下载',
            )
            return
          }
          console.error('重试任务失败：', e)
          return
        }

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

        // 更新 Zustand 状态
        set(state => ({
          tasks: state.tasks.filter(task => task.id !== id),
          currentTaskId: state.currentTaskId === id ? null : state.currentTaskId,
        }))

        // 调用后端删除接口（如果找到了任务）
        if (task) {
          await delete_task({
            video_id: task.audioMeta.video_id,
            platform: task.platform,
          })
        }
      },

      createProject: name => {
        const cleanName = name.trim().slice(0, 50)
        if (!cleanName) return null
        const duplicate = get().projects.some(
          project => project.name.toLocaleLowerCase() === cleanName.toLocaleLowerCase()
        )
        if (duplicate) return null

        const now = new Date().toISOString()
        const project: NoteProject = {
          id: uuidv4(),
          name: cleanName,
          createdAt: now,
          updatedAt: now,
        }
        set(state => ({ projects: [...state.projects, project] }))
        return project
      },

      renameProject: (id, name) => {
        const cleanName = name.trim().slice(0, 50)
        if (!cleanName) return false
        const duplicate = get().projects.some(
          project =>
            project.id !== id
            && project.name.toLocaleLowerCase() === cleanName.toLocaleLowerCase()
        )
        if (duplicate || !get().projects.some(project => project.id === id)) return false

        set(state => ({
          projects: state.projects.map(project =>
            project.id === id
              ? { ...project, name: cleanName, updatedAt: new Date().toISOString() }
              : project
          ),
        }))
        return true
      },

      deleteProject: id =>
        set(state => ({
          projects: state.projects.filter(project => project.id !== id),
          tasks: state.tasks.map(task =>
            task.projectId === id ? { ...task, projectId: null } : task
          ),
          selectedProjectId: state.selectedProjectId === id ? 'all' : state.selectedProjectId,
        })),

      moveTaskToProject: (taskId, projectId) => {
        const target = projectId && get().projects.some(project => project.id === projectId)
          ? projectId
          : null
        set(state => ({
          tasks: state.tasks.map(task =>
            task.id === taskId ? { ...task, projectId: target } : task
          ),
        }))
      },

      moveTasksToProject: (taskIds, projectId) => {
        const ids = new Set(taskIds)
        const target = projectId && get().projects.some(project => project.id === projectId)
          ? projectId
          : null
        set(state => ({
          tasks: state.tasks.map(task =>
            ids.has(task.id) ? { ...task, projectId: target } : task
          ),
        }))
      },

      setSelectedProject: selectedProjectId => set({ selectedProjectId }),
      setHistorySort: historySort => set({ historySort }),

      clearTasks: () => set({ tasks: [], currentTaskId: null }),

      setCurrentTask: taskId => set({ currentTaskId: taskId }),
    }),
    {
      name: 'task-storage',
      version: 2,
      migrate: persistedState => {
        const state = (persistedState || {}) as Partial<TaskStore>
        const projects = Array.isArray(state.projects) ? state.projects : []
        const projectIds = new Set(projects.map(project => project.id))
        const selectedProjectId =
          state.selectedProjectId === 'unfiled'
          || state.selectedProjectId === 'all'
          || projectIds.has(state.selectedProjectId || '')
            ? state.selectedProjectId || 'all'
            : 'all'
        return {
          ...state,
          projects,
          selectedProjectId,
          historySort: state.historySort || 'latest',
          tasks: (state.tasks || []).map(task => ({
            ...task,
            projectId: task.projectId && projectIds.has(task.projectId) ? task.projectId : null,
            lastGeneratedAt: task.lastGeneratedAt || task.createdAt,
          })),
        }
      },
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
