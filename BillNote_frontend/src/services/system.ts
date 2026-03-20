import request from '@/utils/request'

export const systemCheck = async () => {
  return await request.get('/sys_health')
}

export interface DeployStatus {
  backend: {
    status: string
    port: number
  }
  cuda: {
    available: boolean
    version: string | null
    gpu_name: string | null
  }
  whisper: {
    model_size: string
    transcriber_type: string
  }
  ffmpeg: {
    available: boolean
  }
}

export const getDeployStatus = async (): Promise<DeployStatus> => {
  return await request.get('/deploy_status')
}

