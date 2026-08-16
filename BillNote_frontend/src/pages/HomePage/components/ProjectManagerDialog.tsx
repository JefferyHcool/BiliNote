import { useState } from 'react'
import { Folder, Pencil, Save, Trash2, X } from 'lucide-react'
import toast from 'react-hot-toast'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useTaskStore } from '@/store/taskStore'

interface ProjectManagerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const ProjectManagerDialog = ({ open, onOpenChange }: ProjectManagerDialogProps) => {
  const projects = useTaskStore(state => state.projects)
  const tasks = useTaskStore(state => state.tasks)
  const createProject = useTaskStore(state => state.createProject)
  const renameProject = useTaskStore(state => state.renameProject)
  const deleteProject = useTaskStore(state => state.deleteProject)
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')

  const handleCreate = () => {
    const project = createProject(newName)
    if (!project) {
      toast.error(newName.trim() ? '项目名称已存在' : '请输入项目名称')
      return
    }
    setNewName('')
    toast.success(`已创建项目“${project.name}”`)
  }

  const handleRename = (id: string) => {
    if (!renameProject(id, editingName)) {
      toast.error(editingName.trim() ? '项目名称已存在' : '项目名称不能为空')
      return
    }
    setEditingId(null)
    setEditingName('')
  }

  const handleDelete = (id: string, name: string) => {
    const noteCount = tasks.filter(task => task.projectId === id).length
    const message = noteCount > 0
      ? `删除项目“${name}”？其中 ${noteCount} 条笔记会移到“未归类”，笔记不会被删除。`
      : `删除空项目“${name}”？`
    if (!window.confirm(message)) return
    deleteProject(id)
    if (editingId === id) setEditingId(null)
    toast.success('项目已删除，笔记内容已保留')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>管理笔记项目</DialogTitle>
          <DialogDescription>
            项目相当于文件夹。删除项目只会解除归类，不会删除其中的笔记。
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2">
          <Input
            value={newName}
            maxLength={50}
            placeholder="例如：计算机组成与设计"
            onChange={event => setNewName(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') handleCreate()
            }}
          />
          <Button type="button" onClick={handleCreate}>新建</Button>
        </div>

        <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {projects.length === 0 ? (
            <div className="rounded-md border border-dashed py-8 text-center text-sm text-neutral-500">
              暂无项目，请先创建一个文件夹
            </div>
          ) : projects.map(project => {
            const noteCount = tasks.filter(task => task.projectId === project.id).length
            const editing = editingId === project.id
            return (
              <div
                key={project.id}
                className="flex items-center gap-2 rounded-md border border-neutral-200 p-2"
              >
                <Folder className="h-4 w-4 shrink-0 text-blue-500" />
                {editing ? (
                  <Input
                    autoFocus
                    value={editingName}
                    maxLength={50}
                    className="h-8"
                    onChange={event => setEditingName(event.target.value)}
                    onKeyDown={event => {
                      if (event.key === 'Enter') handleRename(project.id)
                      if (event.key === 'Escape') setEditingId(null)
                    }}
                  />
                ) : (
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{project.name}</div>
                    <div className="text-xs text-neutral-500">{noteCount} 条笔记</div>
                  </div>
                )}

                {editing ? (
                  <>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={() => handleRename(project.id)}
                      aria-label="保存项目名称"
                    >
                      <Save className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={() => setEditingId(null)}
                      aria-label="取消重命名"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </>
                ) : (
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8"
                    onClick={() => {
                      setEditingId(project.id)
                      setEditingName(project.name)
                    }}
                    aria-label="重命名项目"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-red-500 hover:text-red-600"
                  onClick={() => handleDelete(project.id, project.name)}
                  aria-label="删除项目"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            )
          })}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default ProjectManagerDialog
