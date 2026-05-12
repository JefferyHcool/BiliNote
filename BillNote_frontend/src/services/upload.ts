import request from '@/utils/request' // 你项目里封装好的axios或者fetch

export const uploadFile = (formData: FormData) => {
  return request.post('/upload', formData, {
    // Local videos can be large and slow over LAN. The global 10s request
    // timeout is useful for normal API calls, but it aborts valid uploads.
    timeout: 0,
  })
}
