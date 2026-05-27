import NoteHistory from '@/pages/HomePage/components/NoteHistory.tsx'
import { useTaskStore } from '@/store/taskStore'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
const History = () => {
  const currentTaskId = useTaskStore(state => state.currentTaskId)
  const setCurrentTask = useTaskStore(state => state.setCurrentTask)
  return (
    <>
      <div className={'flex h-full min-h-0 w-full flex-col px-2.5 py-2'}>
        <ScrollArea className="min-h-0 w-full flex-1">
          {/*<div className="w-full flex-1 overflow-y-auto">*/}
          <NoteHistory onSelect={setCurrentTask} selectedId={currentTaskId} />
          {/*</div>*/}
        </ScrollArea>
      </div>
    </>
  )
}

export default History
