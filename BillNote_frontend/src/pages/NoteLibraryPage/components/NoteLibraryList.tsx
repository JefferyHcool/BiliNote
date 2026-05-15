import { ScrollArea } from '@/components/ui/scroll-area'
import { NoteLibraryRow } from './NoteLibraryRow'
import { LibraryEmptyState } from './LibraryEmptyState'
import type { LibraryNote } from '../hooks/useLibraryNotes'

interface NoteLibraryListProps {
  notes: LibraryNote[]
  selectedId: string | null
  isFiltered: boolean
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  styleLabels: Record<string, string>
  platformLabels: Record<string, string>
  baseURL: string
}

export function NoteLibraryList({
  notes,
  selectedId,
  isFiltered,
  onSelect,
  onDelete,
  styleLabels,
  platformLabels,
  baseURL,
}: NoteLibraryListProps) {
  if (notes.length === 0) {
    return <LibraryEmptyState isFiltered={isFiltered} />
  }

  return (
    <ScrollArea className="h-full">
      {notes.map(note => (
        <NoteLibraryRow
          key={note.id}
          note={note}
          selected={selectedId === note.id}
          onSelect={() => onSelect(note.id)}
          onDelete={() => onDelete(note.id)}
          styleLabel={styleLabels[note.style] || note.style}
          platformLabel={platformLabels[note.platform] || note.platform}
          baseURL={baseURL}
        />
      ))}
    </ScrollArea>
  )
}
