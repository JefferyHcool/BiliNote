import axios, { AxiosInstance, AxiosResponse } from 'axios';
import toast from 'react-hot-toast'

// 统一响应类型
export interface IResponse<T = any> {
  code: number;
  msg: string;
  data: T;
}

// 模拟一个消息提示函数 (实际项目中会使用UI库的组件，如 Ant Design 的 message 或 Element UI 的 ElMessage)
// This function simulates a message display (in real projects, you'd use a UI library's component)


// 创建实例
 const request: AxiosInstance = axios.create({
  baseURL: '/api', // 请确保你的开发服务器代理设置正确
  timeout: 10000,
});

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse<IResponse>) => {
    const res = response.data;
    if (res.code === 0) {
      // 业务成功，可以根据需要显示成功消息，或者不显示（如果操作本身就是可见的）
      // showMessage('success', res.msg || '操作成功'); // 如果需要显示成功消息
      return res.data; // 返回data部分，简化后续业务代码
    } else {
      // 业务错误，统一显示后端返回的错误消息
      // Business error, uniformly display the error message returned from the backend
      toast.error(res.msg || '操作失败，请稍后再试');
      return Promise.reject(res); // 拒绝Promise，让业务代码可以捕获并处理
    }
  },
  (error) => {
    // 网络/服务器错误
    const res = error?.response?.data as IResponse | undefined;
    if (res) {
      // 如果后端有返回错误信息，则显示后端信息
      // If the backend returns an error message, display it

      toast.error(res.msg || '服务器错误，请稍后再试');
      return Promise.reject(res);
    } else {
      // 没有响应数据（如网络中断），显示通用网络错误
      // No response data (e.g., network disconnected), display generic network error
      toast.error( '请求失败，请检查网络连接或稍后再试')
      return Promise.reject({
        code: -1,
        msg: '请求失败，请检查网络连接',
        data: null
      } as IResponse);
    }
  }
);

export default request
