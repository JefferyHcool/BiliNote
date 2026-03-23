import './App.css'
import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import { useTaskPolling } from '@/hooks/useTaskPolling.ts'
import { useCheckBackend } from '@/hooks/useCheckBackend.ts'
import { systemCheck } from '@/services/system.ts'
import BackendInitDialog from '@/components/BackendInitDialog'
import Index from '@/pages/Index.tsx'
import { HomePage } from './pages/HomePage/Home.tsx'

// 非首屏页面使用 React.lazy 按需加载
const SettingPage = lazy(() => import('./pages/SettingPage/index.tsx'))
const Model = lazy(() => import('@/pages/SettingPage/Model.tsx'))
const ProviderForm = lazy(() => import('@/components/Form/modelForm/Form.tsx'))
const AboutPage = lazy(() => import('@/pages/SettingPage/about.tsx'))
const Monitor = lazy(() => import('@/pages/SettingPage/Monitor.tsx'))
const Downloader = lazy(() => import('@/pages/SettingPage/Downloader.tsx'))
const DownloaderForm = lazy(() => import('@/components/Form/DownloaderForm/Form.tsx'))
const TranscriberPage = lazy(() => import('@/pages/SettingPage/transcriber.tsx'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

function App() {
  useTaskPolling(3000) // 每 3 秒轮询一次
  const { loading, initialized } = useCheckBackend()

  // 在后端初始化完成后执行系统检查
  useEffect(() => {
    if (initialized) {
      systemCheck()
    }
  }, [initialized])

  // 如果后端还未初始化，显示初始化对话框
  if (!initialized) {
    return (
      <>
        <BackendInitDialog open={loading} />
      </>
    )
  }

  // 后端已初始化，渲染主应用
  return (
    <>
      <BrowserRouter>
        <Suspense fallback={<div className="flex h-screen items-center justify-center">加载中…</div>}>
          <Routes>
            <Route path="/" element={<Index />}>
              <Route index element={<HomePage />} />
              <Route path="settings" element={<SettingPage />}>
                <Route index element={<Navigate to="model" replace />} />
                <Route path="model" element={<Model />}>
                  <Route path="new" element={<ProviderForm isCreate />} />
                  <Route path=":id" element={<ProviderForm />} />
                </Route>
                <Route path="download" element={<Downloader />}>
                  <Route path=":id" element={<DownloaderForm />} />
                </Route>
                <Route path="transcriber" element={<TranscriberPage />} />
                <Route path="monitor" element={<Monitor />}></Route>
                <Route path="about" element={<AboutPage />}></Route>
                <Route path="*" element={<NotFoundPage />} />
              </Route>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </>
  )
}

export default App
