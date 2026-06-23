import type { ReactNode, FC } from 'react'
// import "@/global.css"
import { Toaster } from 'react-hot-toast'
import { ThemeProvider } from '@/components/ThemeProvider'

interface RootLayoutProps {
  children: ReactNode
}

export const metadata = {
  title: 'BiliNote - 视频笔记生成器',
  description: '通过视频链接结合大模型自动生成对应的笔记',
}

const RootLayout: FC<RootLayoutProps> = ({ children }) => {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background font-sans text-foreground">
        <Toaster
          position="top-center" // 顶部居中显示
          toastOptions={{
            style: {
              borderRadius: '8px',
              background: '#333',
              color: '#fff',
            },
          }}
        />
        {children}
      </div>
    </ThemeProvider>
  )
}

export default RootLayout
