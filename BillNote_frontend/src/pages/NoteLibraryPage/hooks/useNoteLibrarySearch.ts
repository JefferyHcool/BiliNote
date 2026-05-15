import { useState, useEffect, useMemo } from 'react'
import Fuse from 'fuse.js'
import PinyinMatch from 'pinyin-match'
import { useTaskStore } from '@/store/taskStore'

export function useNoteLibrarySearch() {
  const tasks = useTaskStore(state => state.tasks)
  const [rawQuery, setRawQuery] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!rawQuery) {
      setQuery('')
      return
    }
    const t = setTimeout(() => setQuery(rawQuery), 250)
    return () => clearTimeout(t)
  }, [rawQuery])

  const fuse = useMemo(
    () =>
      new Fuse(tasks, {
        keys: ['audioMeta.title', 'formData.model_name', 'formData.style', 'formData.platform'],
        threshold: 0.4,
        includeScore: true,
      }),
    [tasks]
  )

  const matchedIds: string[] | null = useMemo(() => {
    if (!query.trim()) return null

    const fuseResults = fuse.search(query).map(r => r.item.id)
    const fuseSet = new Set(fuseResults)

    // 拼音补充匹配：Fuse 未命中的，用拼音再试一次
    const pinyinExtra = tasks
      .filter(t => !fuseSet.has(t.id) && PinyinMatch.match(t.audioMeta?.title || '', query))
      .map(t => t.id)

    return [...fuseResults, ...pinyinExtra]
  }, [query, fuse, tasks])

  return { rawQuery, setRawQuery, matchedIds }
}
