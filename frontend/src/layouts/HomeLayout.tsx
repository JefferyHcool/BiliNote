import React, { FC } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ResizablePanel, ResizablePanelGroup, ResizableHandle } from '@/components/ui/resizable'
import {ScrollArea} from "@/components/ui/scroll-area.tsx";
import logo from '@/assets/icon.svg'
interface IProps {
  NoteForm: React.ReactNode
  Preview: React.ReactNode
  History: React.ReactNode
}
const HomeLayout: FC<IProps> = ({ NoteForm, Preview, History }) => {
  const [, setShowSettings] = useState(false)

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <ResizablePanelGroup direction="horizontal" className="h-full w-full">
        {/* 左边表单 */}
        <ResizablePanel defaultSize={18} minSize={10} maxSize={35}>
          <aside className="flex h-full flex-col overflow-hidden border-r border-neutral-200 bg-white">
            <header className="flex h-16 items-center justify-between px-6">
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-2xl">
                  <img src={logo} alt="logo" className="h-full w-full object-contain" />
                </div>
                <div className="text-2xl font-bold text-gray-800">BiliNote</div>
              </div>
              <div>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger onClick={() => setShowSettings(true)}>
                      <Link to={'/settings'}>
                        <SlidersHorizontal className="text-muted-foreground hover:text-primary cursor-pointer" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>
                      <span>全局配置</span>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </header>
            <ScrollArea className="flex-1 overflow-auto">
              <div className=' p-4' >{NoteForm}</div>
            </ScrollArea>
          </aside>
        </ResizablePanel>

        <ResizableHandle />

        {/* 中间历史 */}
        <ResizablePanel defaultSize={16} minSize={10} maxSize={30}>
          <aside className="flex h-full flex-col overflow-hidden border-r border-neutral-200 bg-white">
            <ScrollArea className="flex-1 overflow-auto">
            <div className="">{History}</div>
            </ScrollArea>
          </aside>
        </ResizablePanel>

        <ResizableHandle />

        {/* 右边预览 */}
        <ResizablePanel defaultSize={55} minSize={30}>
          <main className="flex h-full flex-col overflow-hidden bg-white p-6">{Preview}</main>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

export default HomeLayout
