import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ChatSource } from '@/services/chat'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: ChatSource[]
}

interface ChatState {
  chatHistory: Record<string, ChatMessage[]>
  addMessage: (taskId: string, msg: ChatMessage) => void
  clearChat: (taskId: string) => void
  getMessages: (taskId: string) => ChatMessage[]
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      chatHistory: {},

      addMessage: (taskId, msg) =>
        set(state => ({
          chatHistory: {
            ...state.chatHistory,
            [taskId]: [...(state.chatHistory[taskId] || []), msg],
          },
        })),

      clearChat: (taskId) =>
        set(state => {
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const { [taskId]: _unused, ...rest } = state.chatHistory
          return { chatHistory: rest }
        }),

      getMessages: (taskId) => get().chatHistory[taskId] || [],
    }),
    {
      name: 'bilinote-chat-storage',
    },
  ),
)
