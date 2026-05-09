import type { Settings } from './types'

export const DEFAULT_BACKEND_URL = 'http://localhost:8483'

export const DEFAULT_SETTINGS: Settings = {
  backendUrl: DEFAULT_BACKEND_URL,
  providerId: '',
  modelName: '',
  quality: 'medium',
  formats: ['toc', 'summary'],
  screenshot: false,
  link: false,
  style: 'minimal',
  extras: '',
}

export const MAX_TASKS = 30

export const SETTINGS_KEY = 'bilinote-settings'
export const TASKS_KEY = 'bilinote-tasks'
