import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { ArrowLeft, SlidersHorizontal } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import logo from '@/assets/icon.svg'
import { useIsMobile } from '@/hooks/useMobile.ts'

interface ISettingLayoutProps {
  Menu: React.ReactNode
}

const SettingLayout = ({ Menu }: ISettingLayoutProps) => {
  const isMobile = useIsMobile()
  const location = useLocation()
  const [showMenu, setShowMenu] = useState(false)

  useEffect(() => {
    if (!isMobile) {
      setShowMenu(true)
      return
    }

    if (location.pathname === '/settings') {
      setShowMenu(true)
      return
    }

    setShowMenu(false)
  }, [isMobile, location.pathname])

  const handleMenuClickCapture = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!isMobile) return
    const target = event.target as HTMLElement
    if (target.closest('a')) {
      setShowMenu(false)
    }
  }

  return (
    <div
      className="h-full w-full"
      style={{
        backgroundColor: 'var(--color-muted)',
      }}
    >
      <div className="flex h-[100dvh] min-h-0 flex-1 flex-col md:flex-row">
        <aside
          className={`flex-col border-r border-neutral-200 bg-white ${
            isMobile ? (showMenu ? 'flex h-full w-full' : 'hidden') : 'flex w-[300px] shrink-0'
          }`}
        >
          <header className="flex h-16 shrink-0 items-center justify-between px-6">
            <div className="flex min-w-0 items-center gap-2">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-2xl">
                <img src={logo} alt="logo" className="h-full w-full object-contain" />
              </div>
              <div className="truncate text-2xl font-bold text-gray-800">BiliNote</div>
            </div>
            <div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link to="/" className="block rounded p-1">
                      <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>返回首页</span>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </header>

          <div className="min-h-0 flex-1 overflow-auto p-4" onClickCapture={handleMenuClickCapture}>
            {Menu}
          </div>
        </aside>

        <main
          className={`min-h-0 flex-1 flex-col overflow-hidden ${
            isMobile && showMenu ? 'hidden' : 'flex'
          }`}
        >
          {isMobile && (
            <div className="flex h-12 shrink-0 items-center border-b border-neutral-200 bg-white px-4">
              <button
                type="button"
                onClick={() => setShowMenu(true)}
                className="flex items-center gap-1 rounded px-2 py-1 text-sm text-neutral-600 hover:bg-neutral-100"
              >
                <ArrowLeft className="h-4 w-4" />
                返回菜单
              </button>
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-hidden">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export default SettingLayout
