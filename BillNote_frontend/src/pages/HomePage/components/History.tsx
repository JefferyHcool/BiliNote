import { useEffect } from 'react'
import NoteHistory from '@/pages/HomePage/components/NoteHistory.tsx'
import { useTaskStore } from '@/store/taskStore'
import { Clock } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import { syncNotes } from '@/services/note.ts'

const History = () => {
  useEffect(() => {
    syncNotes()

    // 定时同步：每 15 秒拉一次后端新任务
    const timer = setInterval(syncNotes, 15000)

    // 页面重新获得焦点时也同步（从其他标签页切回来）
    const onVisible = () => {
      if (document.visibilityState === 'visible') syncNotes()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])
  const currentTaskId = useTaskStore(state => state.currentTaskId)
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)

  const handleSelect = (taskId: string) => {
    setCurrentTask(taskId)
    // 内容加载由 MarkdownViewer 的 effect 负责（空壳任务自动拉取）
  }

  return (
    <>
      <div className={'flex h-full w-full flex-col gap-4 px-2.5 py-1.5'}>
        {/*生成历史    */}
        <div className="my-4 flex h-[40px] items-center gap-2">
          <Clock className="h-4 w-4 text-neutral-500" />
          <h2 className="text-base font-medium text-neutral-900">生成历史</h2>
        </div>
        <ScrollArea className="w-full sm:h-[480px] md:h-[720px] lg:h-[92%]">
          {/*<div className="w-full flex-1 overflow-y-auto">*/}
          <NoteHistory onSelect={handleSelect} selectedId={currentTaskId} />
          {/*</div>*/}
        </ScrollArea>
      </div>
    </>
  )
}

export default History
