import {
  Bold,
  ClipboardPaste,
  Code2,
  Eye,
  Heading2,
  ImagePlus,
  Images,
  Italic,
  Link,
  List,
  ListOrdered,
  Quote,
  RotateCcw,
  Save,
  Trash2,
  X,
} from 'lucide-react'
import {
  type ClipboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import toast from 'react-hot-toast'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { deleteNoteImage, getNoteImageConfig, uploadNoteImage } from '@/services/note'

interface MarkdownEditorProps {
  value: string
  onSave: (content: string) => boolean | Promise<boolean>
  onCancel: () => void
  renderPreview: (content: string) => ReactNode
  onRestoreOriginal?: () => Promise<string | null>
}

interface MarkdownImage {
  alt: string
  url: string
  raw: string
  start: number
  imageId?: string
}

const IMAGE_DIRECTORY_KEY = 'bilinote-editor-image-directory'
const MANAGED_IMAGE_PATTERN = /\/api\/note_images\/([0-9a-f]{32})(?:[?#][^\s)]*)?$/

const parseMarkdownImages = (content: string): MarkdownImage[] => {
  const pattern = /!\[([^\]]*)\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)/g
  const images: MarkdownImage[] = []
  let match: RegExpExecArray | null
  while ((match = pattern.exec(content)) !== null) {
    images.push({
      alt: match[1],
      url: match[2],
      raw: match[0],
      start: match.index,
      imageId: match[2].match(MANAGED_IMAGE_PATTERN)?.[1],
    })
  }
  return images
}

const MarkdownEditor = ({
  value,
  onSave,
  onCancel,
  renderPreview,
  onRestoreOriginal,
}: MarkdownEditorProps) => {
  const [draft, setDraft] = useState(value)
  const [showPreview, setShowPreview] = useState(true)
  const [imageDialogOpen, setImageDialogOpen] = useState(false)
  const [managerOpen, setManagerOpen] = useState(false)
  const [defaultDirectory, setDefaultDirectory] = useState('BiliNote/backend/data/note_images')
  const [useCustomDirectory, setUseCustomDirectory] = useState(false)
  const [customDirectory, setCustomDirectory] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imageAlt, setImageAlt] = useState('')
  const [uploading, setUploading] = useState(false)
  const [pasteUploadCount, setPasteUploadCount] = useState(0)
  const [saving, setSaving] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [pendingFileDeletes, setPendingFileDeletes] = useState<Set<string>>(new Set())
  const newlyUploadedIds = useRef<Set<string>>(new Set())
  const preserveUploadedFiles = useRef(false)
  const editorActive = useRef(true)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const images = useMemo(() => parseMarkdownImages(draft), [draft])
  const isDirty = draft !== value

  useEffect(() => {
    const savedDirectory = localStorage.getItem(IMAGE_DIRECTORY_KEY) || ''
    if (savedDirectory) {
      setCustomDirectory(savedDirectory)
      setUseCustomDirectory(true)
    }
    getNoteImageConfig()
      .then(config => setDefaultDirectory(config.default_directory))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isDirty) return
      event.preventDefault()
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [isDirty])

  useEffect(() => {
    // React StrictMode 会在开发环境执行一次 setup → cleanup → setup。
    // 每次 setup 都恢复 active，避免把随后完成的粘贴上传误判为组件已卸载。
    const uploadedImageIds = newlyUploadedIds
    editorActive.current = true
    return () => {
      editorActive.current = false
      if (!preserveUploadedFiles.current) {
        void Promise.allSettled([...uploadedImageIds.current].map(deleteNoteImage))
      }
    }
  }, [])

  const focusSelection = (start: number, end: number) => {
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
      textareaRef.current?.setSelectionRange(start, end)
    })
  }

  const replaceSelection = (before: string, after: string, placeholder: string) => {
    const textarea = textareaRef.current
    const start = textarea?.selectionStart ?? draft.length
    const end = textarea?.selectionEnd ?? draft.length
    const selected = draft.slice(start, end) || placeholder
    const next = `${draft.slice(0, start)}${before}${selected}${after}${draft.slice(end)}`
    setDraft(next)
    focusSelection(start + before.length, start + before.length + selected.length)
  }

  const insertAtCursor = (text: string) => {
    const textarea = textareaRef.current
    const start = textarea?.selectionStart ?? draft.length
    const end = textarea?.selectionEnd ?? start
    setDraft(`${draft.slice(0, start)}${text}${draft.slice(end)}`)
    focusSelection(start + text.length, start + text.length)
  }

  const uploadPastedImages = (
    files: File[],
    selectionStart: number,
    selectionEnd: number,
  ) => {
    const directory = useCustomDirectory ? customDirectory.trim() : ''
    if (useCustomDirectory && !directory) {
      toast.error('请先填写自定义图片保存目录')
      return
    }

    const uploads = files.map((file, index) => {
      const token = crypto.randomUUID()
      return {
        file,
        placeholder: `<!-- bilinote-paste-upload:${token} -->`,
        alt: file.name && !/^image\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name)
          ? file.name.replace(/\.[^.]+$/, '').replaceAll('[', '').replaceAll(']', '')
          : `粘贴图片${files.length > 1 ? ` ${index + 1}` : ''}`,
      }
    })
    const placeholderText = uploads.map(item => item.placeholder).join('\n')
    setDraft(current => (
      `${current.slice(0, selectionStart)}${placeholderText}${current.slice(selectionEnd)}`
    ))
    focusSelection(
      selectionStart + placeholderText.length,
      selectionStart + placeholderText.length,
    )
    setPasteUploadCount(count => count + uploads.length)

    void Promise.allSettled(uploads.map(async item => {
      try {
        const uploaded = await uploadNoteImage(item.file, directory)
        if (!editorActive.current) {
          await deleteNoteImage(uploaded.id)
          return
        }
        newlyUploadedIds.current.add(uploaded.id)
        if (directory) localStorage.setItem(IMAGE_DIRECTORY_KEY, directory)
        setDraft(current => current.replace(
          item.placeholder,
          `![${item.alt}](${uploaded.url})`,
        ))
      } catch {
        if (editorActive.current) {
          setDraft(current => current.replace(item.placeholder, ''))
        }
        throw new Error('paste image upload failed')
      } finally {
        if (editorActive.current) setPasteUploadCount(count => Math.max(0, count - 1))
      }
    })).then(results => {
      if (!editorActive.current) return
      const succeeded = results.filter(result => result.status === 'fulfilled').length
      if (succeeded > 0) toast.success(`已粘贴 ${succeeded} 张图片`)
    })
  }

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const imageFiles = Array.from(event.clipboardData.items)
      .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
      .map(item => item.getAsFile())
      .filter((file): file is File => file !== null)

    if (imageFiles.length === 0) return

    event.preventDefault()
    uploadPastedImages(
      imageFiles,
      event.currentTarget.selectionStart,
      event.currentTarget.selectionEnd,
    )
  }

  const prefixLines = (prefix: string) => {
    const textarea = textareaRef.current
    const start = textarea?.selectionStart ?? draft.length
    const end = textarea?.selectionEnd ?? draft.length
    const lineStart = draft.lastIndexOf('\n', Math.max(0, start - 1)) + 1
    const selected = draft.slice(lineStart, end) || '内容'
    const replacement = selected.split('\n').map(line => `${prefix}${line}`).join('\n')
    setDraft(`${draft.slice(0, lineStart)}${replacement}${draft.slice(end)}`)
    focusSelection(lineStart, lineStart + replacement.length)
  }

  const insertUploadedImage = async () => {
    if (!imageFile) {
      toast.error('请先选择图片')
      return
    }
    const directory = useCustomDirectory ? customDirectory.trim() : ''
    if (useCustomDirectory && !directory) {
      toast.error('请输入自定义保存目录')
      return
    }

    setUploading(true)
    try {
      const uploaded = await uploadNoteImage(imageFile, directory)
      newlyUploadedIds.current.add(uploaded.id)
      if (directory) localStorage.setItem(IMAGE_DIRECTORY_KEY, directory)
      else localStorage.removeItem(IMAGE_DIRECTORY_KEY)

      const alt = imageAlt.trim() || imageFile.name.replace(/\.[^.]+$/, '') || '图片'
      insertAtCursor(`![${alt}](${uploaded.url})`)
      setImageDialogOpen(false)
      setImageFile(null)
      setImageAlt('')
      toast.success(`图片已保存到 ${uploaded.directory}`)
    } catch {
      // 请求层已经展示具体错误。
    } finally {
      setUploading(false)
    }
  }

  const removeImageReference = (image: MarkdownImage, deleteFile: boolean) => {
    if (deleteFile && !window.confirm('确定同时删除这张本地图片文件吗？该操作保存后不可恢复。')) {
      return
    }
    setDraft(current => {
      const before = current.slice(0, image.start)
      const target = current.slice(image.start, image.start + image.raw.length)
      if (target !== image.raw) return current.replace(image.raw, '')
      return before + current.slice(image.start + image.raw.length)
    })
    if (deleteFile && image.imageId) {
      setPendingFileDeletes(current => new Set(current).add(image.imageId!))
    }
  }

  const handleCancel = () => {
    if (isDirty && !window.confirm('放弃尚未保存的修改吗？')) return
    const imagesToDiscard = [...newlyUploadedIds.current]
    newlyUploadedIds.current.clear()
    preserveUploadedFiles.current = true
    onCancel()
    void Promise.allSettled(imagesToDiscard.map(deleteNoteImage))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      preserveUploadedFiles.current = true
      const saved = await onSave(draft)
      if (!saved) {
        preserveUploadedFiles.current = false
        toast.error('笔记保存失败')
        return
      }
      await Promise.allSettled([...pendingFileDeletes].map(deleteNoteImage))
      newlyUploadedIds.current.clear()
      setPendingFileDeletes(new Set())
      toast.success('笔记已保存')
    } catch {
      preserveUploadedFiles.current = false
      toast.error('笔记保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleRestoreOriginal = async () => {
    if (!onRestoreOriginal) return
    if (!window.confirm('用后端保存的原始生成稿替换当前编辑内容吗？替换后仍需点击“保存”才会生效。')) {
      return
    }
    setRestoring(true)
    try {
      const original = await onRestoreOriginal()
      if (!original) {
        toast.error('未找到原始生成稿')
        return
      }
      setDraft(original)
      toast.success('已载入原始生成稿，请确认后保存')
    } catch {
      toast.error('读取原始生成稿失败')
    } finally {
      setRestoring(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-white">
      <div className="flex flex-wrap items-center gap-1 border-b bg-neutral-50 px-3 py-2">
        <Button type="button" variant="ghost" size="icon" title="二级标题" onClick={() => prefixLines('## ')}>
          <Heading2 className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="加粗" onClick={() => replaceSelection('**', '**', '粗体文字')}>
          <Bold className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="斜体" onClick={() => replaceSelection('*', '*', '斜体文字')}>
          <Italic className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="代码块" onClick={() => replaceSelection('```text\n', '\n```', '代码')}>
          <Code2 className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="无序列表" onClick={() => prefixLines('- ')}>
          <List className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="有序列表" onClick={() => prefixLines('1. ')}>
          <ListOrdered className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="引用" onClick={() => prefixLines('> ')}>
          <Quote className="h-4 w-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" title="链接" onClick={() => replaceSelection('[', '](https://)', '链接文字')}>
          <Link className="h-4 w-4" />
        </Button>
        <div className="mx-1 h-5 w-px bg-neutral-300" />
        <Button type="button" variant="ghost" size="sm" onClick={() => setImageDialogOpen(true)}>
          <ImagePlus className="h-4 w-4" />
          插入图片
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setManagerOpen(true)}>
          <Images className="h-4 w-4" />
          图片管理（{images.length}）
        </Button>
        <span className="ml-1 hidden items-center gap-1 text-xs text-neutral-500 xl:flex">
          <ClipboardPaste className="h-3.5 w-3.5" />
          {pasteUploadCount > 0 ? `正在上传 ${pasteUploadCount} 张…` : '可直接 Ctrl+V 粘贴图片'}
        </span>
        <div className="ml-auto flex items-center gap-1">
          {onRestoreOriginal && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={restoring || pasteUploadCount > 0}
              onClick={handleRestoreOriginal}
            >
              <RotateCcw className="h-4 w-4" />
              {restoring ? '读取中…' : '恢复生成稿'}
            </Button>
          )}
          <Button type="button" variant={showPreview ? 'secondary' : 'ghost'} size="sm" onClick={() => setShowPreview(value => !value)}>
            <Eye className="h-4 w-4" />
            实时预览
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={handleCancel}>
            <X className="h-4 w-4" />
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={!isDirty || saving || pasteUploadCount > 0}
            onClick={handleSave}
          >
            <Save className="h-4 w-4" />
            {saving ? '保存中…' : '保存'}
          </Button>
        </div>
      </div>

      <div className={`grid min-h-0 flex-1 ${showPreview ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'}`}>
        <textarea
          ref={textareaRef}
          value={draft}
          onChange={event => setDraft(event.target.value)}
          onPaste={handlePaste}
          spellCheck={false}
          className="h-full min-h-[400px] w-full resize-none border-0 bg-neutral-950 p-5 font-mono text-sm leading-6 text-neutral-100 outline-none"
          placeholder="在这里编辑 Markdown…"
        />
        {showPreview && (
          <ScrollArea className="min-h-0 border-l bg-white">
            <div className="markdown-body px-5 py-3">
              {draft.trim() ? renderPreview(draft) : (
                <p className="text-sm text-neutral-400">预览区域</p>
              )}
            </div>
          </ScrollArea>
        )}
      </div>

      <Dialog open={imageDialogOpen} onOpenChange={setImageDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>插入图片</DialogTitle>
            <DialogDescription>上传完成后会在光标位置插入标准 Markdown 图片语法。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="note-image-file">图片文件</Label>
              <Input
                id="note-image-file"
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp,image/bmp,image/svg+xml"
                onChange={event => setImageFile(event.target.files?.[0] || null)}
              />
              <p className="text-xs text-neutral-500">支持 PNG、JPG、GIF、WebP、BMP、SVG，最大 15 MB。</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="note-image-alt">图片说明（Alt）</Label>
              <Input id="note-image-alt" value={imageAlt} onChange={event => setImageAlt(event.target.value)} placeholder="例如：RISC-V 五级流水线" />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={useCustomDirectory} onCheckedChange={checked => setUseCustomDirectory(checked === true)} />
              使用自定义保存目录
            </label>
            {useCustomDirectory ? (
              <div className="space-y-2">
                <Label htmlFor="note-image-directory">本机目录</Label>
                <Input id="note-image-directory" value={customDirectory} onChange={event => setCustomDirectory(event.target.value)} placeholder="例如：/home/user/Pictures/BiliNote" />
                <p className="text-xs text-neutral-500">相对路径会从 BiliNote 项目根目录开始解析。</p>
              </div>
            ) : (
              <div className="rounded-md bg-neutral-100 p-3 text-xs text-neutral-600">
                默认保存位置：<span className="break-all font-mono">{defaultDirectory}</span>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setImageDialogOpen(false)}>取消</Button>
            <Button type="button" disabled={!imageFile || uploading} onClick={insertUploadedImage}>
              {uploading ? '上传中…' : '上传并插入'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={managerOpen} onOpenChange={setManagerOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>管理正文图片</DialogTitle>
            <DialogDescription>
              “移除引用”只修改当前笔记；“删除文件”会在保存笔记后同时删除编辑器上传的本地图片。
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[55vh]">
            <div className="space-y-2 pr-3">
              {images.length === 0 ? (
                <div className="rounded-md border border-dashed py-8 text-center text-sm text-neutral-500">正文中没有图片</div>
              ) : images.map((image, index) => (
                <div key={`${image.start}-${image.url}`} className="flex items-center gap-3 rounded-md border p-2">
                  <img src={image.url} alt={image.alt} className="h-16 w-24 shrink-0 rounded border object-cover" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{image.alt || `图片 ${index + 1}`}</p>
                    <p className="truncate text-xs text-neutral-500">{image.url}</p>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={() => removeImageReference(image, false)}>
                    移除引用
                  </Button>
                  {image.imageId && (
                    <Button type="button" variant="destructive" size="sm" onClick={() => removeImageReference(image, true)}>
                      <Trash2 className="h-4 w-4" />
                      删除文件
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default MarkdownEditor
