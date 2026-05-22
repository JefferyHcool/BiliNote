import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { AudioLines, AlertTriangle, CheckCircle2, Download, Loader2, Save, XCircle, Plus, Trash2, Boxes } from 'lucide-react'
import { toast } from 'react-hot-toast'
import {
  getTranscriberConfig,
  updateTranscriberConfig,
  getModelsStatus,
  downloadModel,
  addWhisperModel,
  deleteWhisperModel,
  TranscriberConfig,
  ModelStatus,
} from '@/services/transcriber'

const isWhisperType = (type: string) =>
  type === 'fast-whisper' || type === 'mlx-whisper'

export default function Transcriber() {
  const [config, setConfig] = useState<TranscriberConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [selectedType, setSelectedType] = useState('')
  const [selectedModelSize, setSelectedModelSize] = useState('')
  const [modelStatuses, setModelStatuses] = useState<ModelStatus[]>([])
  const [mlxModelStatuses, setMlxModelStatuses] = useState<ModelStatus[]>([])
  const [mlxAvailable, setMlxAvailable] = useState(false)
  // 自定义模型表单
  const [newModelName, setNewModelName] = useState('')
  const [newModelTarget, setNewModelTarget] = useState('')
  const [addingModel, setAddingModel] = useState(false)

  // 重新拉取配置（不重置用户当前的选择），用于增删自定义模型后刷新下拉与列表
  const reloadConfig = useCallback(async () => {
    try {
      setConfig(await getTranscriberConfig())
    } catch {
      // 静默
    }
  }, [])

  const fetchModelsStatus = useCallback(async () => {
    try {
      const data = await getModelsStatus()
      setModelStatuses(data.whisper)
      setMlxModelStatuses(data.mlx_whisper)
      setMlxAvailable(data.mlx_available)
    } catch {
      // 静默失败，不阻塞主流程
    }
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getTranscriberConfig()
        setConfig(data)
        setSelectedType(data.transcriber_type)
        setSelectedModelSize(data.whisper_model_size)
      } catch {
        toast.error('获取转写器配置失败')
      } finally {
        setLoading(false)
      }
    }
    load()
    fetchModelsStatus()
  }, [fetchModelsStatus])

  // 有下载中的模型时自动轮询状态
  useEffect(() => {
    const hasDownloading =
      modelStatuses.some(m => m.downloading) || mlxModelStatuses.some(m => m.downloading)
    if (!hasDownloading) return

    const timer = setInterval(fetchModelsStatus, 3000)
    return () => clearInterval(timer)
  }, [modelStatuses, mlxModelStatuses, fetchModelsStatus])

  const handleSave = async () => {
    // 切到本地 whisper 引擎且选了未下载的模型时，提前 confirm，避免用户保存后到首次任务才发现要下 GB 级模型
    if (isWhisperType(selectedType)) {
      const pool = selectedType === 'mlx-whisper' ? mlxModelStatuses : modelStatuses
      const target = pool.find(m => m.model_size === selectedModelSize)
      if (target && !target.downloaded && !target.downloading) {
        const sizeHint: Record<string, string> = {
          'tiny': '~75MB',
          'base': '~150MB',
          'small': '~500MB',
          'medium': '~1.5GB',
          'large-v3': '~3GB',
          'large-v3-turbo': '~1.6GB',
        }
        const ok = window.confirm(
          `选择 ${selectedType} / ${selectedModelSize} 后，首次转写时会下载该模型（${sizeHint[selectedModelSize] || '体积未知'}）。\n` +
          `网络较差时容易中断；推荐改用 Groq / 必剪 / 快手 等在线引擎。\n\n` +
          '继续保存吗？',
        )
        if (!ok) return
      }
    }

    setSaving(true)
    try {
      const payload: { transcriber_type: string; whisper_model_size?: string } = {
        transcriber_type: selectedType,
      }
      if (isWhisperType(selectedType)) {
        payload.whisper_model_size = selectedModelSize
      }
      await updateTranscriberConfig(payload)
      toast.success('转写器配置已保存')
    } catch {
      toast.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDownload = async (modelSize: string, transcriberType: string) => {
    try {
      await downloadModel({ model_size: modelSize, transcriber_type: transcriberType })
      toast.success(`模型 ${modelSize} 开始下载`)
      // 立即刷新状态
      setTimeout(fetchModelsStatus, 1000)
    } catch {
      toast.error('下载请求失败')
    }
  }

  const handleAddCustomModel = async () => {
    const name = newModelName.trim()
    const target = newModelTarget.trim()
    if (!name || !target) {
      toast.error('请填写模型名称和 HF repo_id / 本地路径')
      return
    }
    setAddingModel(true)
    try {
      await addWhisperModel({ name, target })
      toast.success(`已添加自定义模型 ${name}`)
      setNewModelName('')
      setNewModelTarget('')
      await reloadConfig()
      await fetchModelsStatus()
    } catch {
      // 后端的具体错误（如重名）已由请求拦截器 toast，这里不重复提示
    } finally {
      setAddingModel(false)
    }
  }

  const handleDeleteCustomModel = async (name: string) => {
    try {
      await deleteWhisperModel(name)
      toast.success(`已删除自定义模型 ${name}`)
      // 删的正好是当前选中的，回退到 tiny，避免选中一个不存在的名称
      if (selectedModelSize === name) setSelectedModelSize('tiny')
      await reloadConfig()
      await fetchModelsStatus()
    } catch {
      // 拦截器已提示
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
      </div>
    )
  }

  if (!config) {
    return <div className="p-6 text-center text-neutral-500">无法加载配置</div>
  }

  const currentModels = selectedType === 'mlx-whisper' ? mlxModelStatuses : modelStatuses

  return (
    <div className="space-y-6 p-6">
      <div>
        <h2 className="text-2xl font-semibold">音频转写配置</h2>
        <p className="mt-1 text-sm text-neutral-500">
          选择视频音频转写为文字所使用的引擎，保存后对新任务立即生效
        </p>
      </div>

      {/* 转写引擎选择 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <AudioLines className="h-5 w-5" />
            转写引擎
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">转写器类型</label>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger className="w-full max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {config.available_types.map(t => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isWhisperType(selectedType) && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Whisper 模型大小</label>
              <Select value={selectedModelSize} onValueChange={setSelectedModelSize}>
                <SelectTrigger className="w-full max-w-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {config.whisper_model_sizes.map(size => {
                    const status = currentModels.find(m => m.model_size === size)
                    return (
                      <SelectItem key={size} value={size}>
                        <span className="flex items-center gap-2">
                          {size}
                          {status?.downloaded && (
                            <CheckCircle2 className="h-3 w-3 text-green-500" />
                          )}
                        </span>
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
              <p className="text-xs text-neutral-400">
                模型越大精度越高，但速度更慢、占用更多显存
              </p>
            </div>
          )}

          {selectedType === 'mlx-whisper' && !config.mlx_whisper_available && (
            <Alert variant="warning" className="text-sm">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                MLX Whisper 当前不可用。需要 macOS 平台并安装{' '}
                <code className="rounded bg-neutral-100 px-1">pip install mlx_whisper</code>，
                安装后重启后端生效。
              </AlertDescription>
            </Alert>
          )}

          <Button onClick={handleSave} disabled={saving || (selectedType === 'mlx-whisper' && !config.mlx_whisper_available)} className="mt-2">
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            保存配置
          </Button>
        </CardContent>
      </Card>

      {/* Whisper 模型管理 */}
      {isWhisperType(selectedType) && currentModels.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Download className="h-5 w-5" />
              模型管理
              <span className="text-sm font-normal text-neutral-400">
                {selectedType === 'mlx-whisper' ? 'MLX Whisper' : 'Faster Whisper'}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {currentModels.map(model => (
                <div
                  key={model.model_size}
                  className="flex items-center justify-between rounded-md border px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{model.model_size}</span>
                    {model.downloaded ? (
                      <Badge variant="default" className="bg-green-500 hover:bg-green-600">
                        已下载
                      </Badge>
                    ) : model.downloading ? (
                      <Badge variant="secondary" className="flex items-center gap-1">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        下载中
                      </Badge>
                    ) : (
                      <Badge variant="outline">未下载</Badge>
                    )}
                  </div>
                  {!model.downloaded && !model.downloading && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDownload(model.model_size, selectedType)}
                    >
                      <Download className="mr-1 h-4 w-4" />
                      下载
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 自定义 Whisper 模型（仅 fast-whisper：名称不符合内置 Systran 约定的模型在此登记映射） */}
      {selectedType === 'fast-whisper' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Boxes className="h-5 w-5" />
              自定义模型
              <span className="text-sm font-normal text-neutral-400">
                登记名称不符合内置约定的模型
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert className="text-sm">
              <AlertDescription>
                填 <strong>HF repo_id</strong>（如{' '}
                <code className="rounded bg-neutral-100 px-1">Systran/faster-whisper-large-v3</code>
                ，会自动下载）或<strong>本地模型目录</strong>（如{' '}
                <code className="rounded bg-neutral-100 px-1">/app/backend/models/my-whisper</code>
                ，目录内需含 <code className="rounded bg-neutral-100 px-1">model.bin</code>，下载会跳过）。
                添加后即可在上方「模型大小」下拉中选用。Docker 部署请把模型目录挂载进容器（见 README 的{' '}
                <code className="rounded bg-neutral-100 px-1">models</code> 卷）。
              </AlertDescription>
            </Alert>

            {config.whisper_custom_models &&
            Object.keys(config.whisper_custom_models).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(config.whisper_custom_models).map(([name, target]) => {
                  const status = modelStatuses.find(m => m.model_size === name)
                  return (
                    <div
                      key={name}
                      className="flex items-center justify-between gap-3 rounded-md border px-4 py-2.5"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 font-medium">
                          {name}
                          {status?.downloaded && (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                          )}
                          {status?.downloading && (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-neutral-400" />
                          )}
                        </div>
                        <div className="truncate text-xs text-neutral-400" title={target}>
                          {target}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:text-red-600"
                        onClick={() => handleDeleteCustomModel(name)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm text-neutral-400">还没有自定义模型</p>
            )}

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Input
                placeholder="模型名称（自定义，如 my-large-v3）"
                value={newModelName}
                onChange={e => setNewModelName(e.target.value)}
                className="sm:max-w-[220px]"
              />
              <Input
                placeholder="HF repo_id 或本地路径"
                value={newModelTarget}
                onChange={e => setNewModelTarget(e.target.value)}
                className="flex-1"
              />
              <Button onClick={handleAddCustomModel} disabled={addingModel}>
                {addingModel ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="mr-1 h-4 w-4" />
                )}
                添加
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
