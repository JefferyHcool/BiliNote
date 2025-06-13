// src/pages/NotFoundPage.tsx
import NotFound from '@/components/Lottie/404.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useNavigate } from 'react-router-dom'

const NotFoundPage = () => {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center text-gray-500">
      <div className="text-center">
        <h1 className="mb-4 text-4xl font-bold">你好像走丢了哦！～～</h1>
        <p className="mb-4 text-lg">请检查你的网址是否正确，或者点击下面的按钮返回首页。</p>
        <Button onClick={() => navigate('/')} className="hover:underline">
          返回首页
        </Button>
      </div>
      <div>
        <NotFound />
      </div>
    </div>
  )
}

export default NotFoundPage
