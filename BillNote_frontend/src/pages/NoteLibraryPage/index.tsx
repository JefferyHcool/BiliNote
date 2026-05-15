import { useState, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable'
import { useTaskStore } from '@/store/taskStore'
import { syncNotes } from '@/services/note'
import { LibraryToolbar } from './components/LibraryToolbar'
import { NoteLibraryList } from './components/NoteLibraryList'
import { NoteDetailPanel } from './components/NoteDetailPanel'
import { useLibraryNotes, useLibraryOptions, type LibraryFilters } from './hooks/useLibraryNotes'
import { useNoteLibrarySearch } from './hooks/useNoteLibrarySearch'

const DEFAULT_FILTERS: LibraryFilters = {
  status: 'success',
  model: '',
  style: '',
  platform: '',
  sort: 'desc',
}

export default function NoteLibraryPage() {
  const baseURL = String(import.meta.env.VITE_API_BASE_URL || 'api').replace(/\/$/, '')
  const removeTask = useTaskStore(state => state.removeTask)

  const [filters, setFilters] = useState<LibraryFilters>(DEFAULT_FILTERS)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { rawQuery, setRawQuery, matchedIds } = useNoteLibrarySearch()
  const options = useLibraryOptions()

  const isFiltered =
    filters.status !== 'success' ||
    filters.model !== '' ||
    filters.style !== '' ||
    filters.platform !== '' ||
    rawQuery !== ''

  const notes = useLibraryNotes(filters, matchedIds)

  // Sync from backend on mount
  useEffect(() => {
    syncNotes()
  }, [])

  const handleFiltersChange = useCallback((patch: Partial<LibraryFilters>) => {
    setFilters(prev => ({ ...prev, ...patch }))
  }, [])

  const handleSelect = useCallback((id: string) => {
    setSelectedId(prev => (prev === id ? null : id))
  }, [])

  const handleDelete = useCallback(
    async (id: string) => {
      await removeTask(id)
      if (selectedId === id) setSelectedId(null)
    },
    [selectedId, removeTask]
  )

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      {/* 顶部导航 */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b px-4">
        <h1 className="text-base font-semibold text-gray-800">笔记库</h1>
        <Link
          to="/"
          className="flex items-center gap-1.5 rounded px-2 py-1 text-sm text-gray-500 hover:bg-neutral-100 hover:text-gray-700"
        >
          <Home className="h-4 w-4" />
          <span>返回首页</span>
        </Link>
      </header>

      <ResizablePanelGroup direction="horizontal" className="flex-1 overflow-hidden">
        {/* 左侧列表 */}
        <ResizablePanel defaultSize={38} minSize={25} maxSize={55}>
          <div className="flex h-full flex-col overflow-hidden">
            <LibraryToolbar
              query={rawQuery}
              onQueryChange={setRawQuery}
              filters={filters}
              onFiltersChange={handleFiltersChange}
              models={options.models}
              platforms={options.platforms}
              styles={options.styles}
              total={notes.length}
            />
            <div className="flex-1 overflow-hidden">
              <NoteLibraryList
                notes={notes}
                selectedId={selectedId}
                isFiltered={isFiltered}
                onSelect={handleSelect}
                onDelete={handleDelete}
                styleLabels={options.styleLabels}
                platformLabels={options.platformLabels}
                baseURL={baseURL}
              />
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle />

        {/* 右侧详情 */}
        <ResizablePanel defaultSize={62} minSize={40}>
          <NoteDetailPanel noteId={selectedId} onDelete={handleDelete} />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
