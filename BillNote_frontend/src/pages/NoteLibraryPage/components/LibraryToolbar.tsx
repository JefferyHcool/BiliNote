import { Search, ArrowDownUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { LibraryFilters, StatusFilter } from '../hooks/useLibraryNotes'

interface LibraryToolbarProps {
  query: string
  onQueryChange: (v: string) => void
  filters: LibraryFilters
  onFiltersChange: (f: Partial<LibraryFilters>) => void
  models: string[]
  platforms: { value: string; label: string }[]
  styles: { value: string; label: string }[]
  total: number
}

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: '全部状态' },
  { value: 'success', label: '已完成' },
  { value: 'running', label: '运行中' },
  { value: 'failed', label: '失败' },
]

export function LibraryToolbar({
  query,
  onQueryChange,
  filters,
  onFiltersChange,
  models,
  platforms,
  styles,
  total,
}: LibraryToolbarProps) {
  const hasActiveFilter =
    filters.status !== 'success' ||
    filters.model !== '' ||
    filters.style !== '' ||
    filters.platform !== '' ||
    query !== ''

  return (
    <div className="flex flex-col gap-2 border-b bg-white px-4 py-3">
      {/* 搜索框 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={e => onQueryChange(e.target.value)}
          placeholder="搜索标题、模型、风格…"
          className="w-full rounded-md border border-neutral-200 py-1.5 pl-9 pr-3 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/30"
        />
      </div>

      {/* 筛选器行 */}
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={filters.status}
          onValueChange={v => onFiltersChange({ status: v as StatusFilter })}
        >
          <SelectTrigger className="h-7 w-[100px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map(o => (
              <SelectItem key={o.value} value={o.value} className="text-xs">
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {models.length > 0 && (
          <Select
            value={filters.model || '__all__'}
            onValueChange={v => onFiltersChange({ model: v === '__all__' ? '' : v })}
          >
            <SelectTrigger className="h-7 w-[120px] text-xs">
              <SelectValue placeholder="全部模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__" className="text-xs">全部模型</SelectItem>
              {models.map(m => (
                <SelectItem key={m} value={m} className="text-xs">{m}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {styles.length > 0 && (
          <Select
            value={filters.style || '__all__'}
            onValueChange={v => onFiltersChange({ style: v === '__all__' ? '' : v })}
          >
            <SelectTrigger className="h-7 w-[90px] text-xs">
              <SelectValue placeholder="全部风格" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__" className="text-xs">全部风格</SelectItem>
              {styles.map(s => (
                <SelectItem key={s.value} value={s.value} className="text-xs">{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {platforms.length > 0 && (
          <Select
            value={filters.platform || '__all__'}
            onValueChange={v => onFiltersChange({ platform: v === '__all__' ? '' : v })}
          >
            <SelectTrigger className="h-7 w-[90px] text-xs">
              <SelectValue placeholder="全部平台" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__" className="text-xs">全部平台</SelectItem>
              {platforms.map(p => (
                <SelectItem key={p.value} value={p.value} className="text-xs">{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs text-gray-500"
          onClick={() => onFiltersChange({ sort: filters.sort === 'desc' ? 'asc' : 'desc' })}
        >
          <ArrowDownUp className="mr-1 h-3 w-3" />
          {filters.sort === 'desc' ? '最新优先' : '最早优先'}
        </Button>

        <span className="ml-auto text-xs text-gray-400">{total} 篇笔记</span>

        {hasActiveFilter && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-gray-400 hover:text-gray-700"
            onClick={() => {
              onQueryChange('')
              onFiltersChange({ status: 'success', model: '', style: '', platform: '' })
            }}
          >
            清除筛选
          </Button>
        )}
      </div>
    </div>
  )
}
