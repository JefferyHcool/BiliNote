import { BookOpen, Search } from 'lucide-react'

interface LibraryEmptyStateProps {
  isFiltered: boolean
}

export function LibraryEmptyState({ isFiltered }: LibraryEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-gray-400">
      {isFiltered ? (
        <>
          <Search className="h-10 w-10 opacity-40" />
          <p className="text-sm">没有符合条件的笔记</p>
          <p className="text-xs">尝试调整筛选条件或搜索关键词</p>
        </>
      ) : (
        <>
          <BookOpen className="h-10 w-10 opacity-40" />
          <p className="text-sm">笔记库为空</p>
          <p className="text-xs">在首页生成第一篇笔记后，这里会显示所有笔记</p>
        </>
      )}
    </div>
  )
}
