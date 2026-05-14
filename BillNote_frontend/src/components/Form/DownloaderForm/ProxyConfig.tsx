import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { getProxyConfig, updateProxyConfig } from '@/services/proxy'

// 全局代理配置：作用于 LLM API + 转写 API（Groq 等）+ yt-dlp 视频下载。
// 国内访问 OpenAI / Groq / YouTube 基本都要靠它。
const ProxyConfig = () => {
  const [enabled, setEnabled] = useState(false)
  const [url, setUrl] = useState('')
  const [effective, setEffective] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    ;(async () => {
      try {
        const cfg = await getProxyConfig()
        setEnabled(cfg.enabled)
        setUrl(cfg.url)
        setEffective(cfg.effective)
      } catch {
        /* 拦截器已 toast */
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const handleSave = async () => {
    if (enabled && !url.trim()) {
      toast.error('请填写代理地址，或关闭代理开关')
      return
    }
    setSaving(true)
    try {
      const cfg = await updateProxyConfig({ enabled, url: url.trim() })
      setEnabled(cfg.enabled)
      setUrl(cfg.url)
      setEffective(cfg.effective)
      toast.success('代理配置已保存')
    } catch {
      /* 拦截器已 toast */
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="text-xs text-gray-400">加载代理配置…</div>
  }

  // env 兜底：配置没开但 effective 有值，说明来自 HTTP_PROXY 环境变量
  const fromEnv = !enabled && !!effective

  return (
    <div className="flex flex-col gap-2 rounded border border-neutral-200 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">全局代理</span>
        <Switch checked={enabled} onCheckedChange={setEnabled} />
      </div>
      <p className="text-xs text-gray-400">
        作用于 AI 模型接口、转写接口（Groq 等）、YouTube 下载。
      </p>
      <Input
        placeholder="http://127.0.0.1:7890"
        value={url}
        disabled={!enabled}
        onChange={e => setUrl(e.target.value)}
        className="text-sm"
      />
      {fromEnv && (
        <p className="text-xs text-amber-600">
          当前生效（来自环境变量）：{effective}
        </p>
      )}
      {enabled && effective && (
        <p className="text-xs text-green-600">当前生效：{effective}</p>
      )}
      <Button size="sm" onClick={handleSave} disabled={saving}>
        {saving ? '保存中…' : '保存代理配置'}
      </Button>
    </div>
  )
}

export default ProxyConfig
