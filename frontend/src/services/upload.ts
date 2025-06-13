import request from '@/utils/request' // 你项目里封装好的axios或者fetch

export const uploadFile = (formData: FormData) => {
  return request.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}
