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
import { AudioLines, AlertTriangle, CheckCircle2, Download, Loader2, Save } from 'lucide-react'
import { toast } from 'react-hot-toast'
import {
  getTranscriberConfig,
  updateTranscriberConfig,
  getModelsStatus,
  downloadModel,
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

  const fetchModelsStatus = useCallback(async () => {
    try {
      const data = await getModelsStatus()
      setModelStatuses(data.whisper)
      setMlxModelStatuses(data.mlx_whisper)
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
    </div>
  )
}
