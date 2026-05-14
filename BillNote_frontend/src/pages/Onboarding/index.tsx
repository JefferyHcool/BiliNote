import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { addProvider, addModel, testConnection, getProviderList, updateProviderById } from '@/services/model'
import { getTranscriberConfig, updateTranscriberConfig } from '@/services/transcriber'
import logo from '@/assets/icon.svg'

// 后端 R.error / ProviderError 的形状是 { code, msg, data }，没有 .message。
// 直接 ${e} 会渲染成 [object Object]，这里统一抽取可读文案。
function errText(e: any): string {
  if (!e) return '未知错误'
  if (typeof e === 'string') return e
  return e.msg || e.message || JSON.stringify(e)
}

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

// 后端连通性自检不走共享 axios（会弹 toast），用裸 fetch 避免启动期 toast 叠堆
function getBackendBase(): string {
  const fromEnv = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined
  return ((fromEnv && fromEnv.length > 0) ? fromEnv : '/api').replace(/\/$/, '')
}
async function pingBackend(): Promise<boolean> {
  try {
    const res = await fetch(`${getBackendBase()}/sys_check`)
    if (!res.ok) return false
    const json = await res.json().catch(() => null)
    return json?.code === 0
  }
  catch {
    return false
  }
}

// 桌面端首启 4 步引导。完成后写 localStorage('bilinote-onboarded') = '1'，路由守卫不再拦。
//
// 1. 后端连通性自检
// 2. LLM 供应商 + 模型（最简：只引导填一个 OpenAI-兼容供应商 + 一个 model 名）
// 3. 转写引擎选择（推荐 Groq 在线，避开本地模型下载坑）
// 4. （可选）Cookie 同步说明（仅当用户关注 B 站等需要登录态的平台时）

const ONBOARD_KEY = 'bilinote-onboarded'

export function isOnboarded(): boolean {
  return localStorage.getItem(ONBOARD_KEY) === '1'
}

function markOnboarded() {
  localStorage.setItem(ONBOARD_KEY, '1')
}

const Onboarding = () => {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')

  // step 1
  const [pinging, setPinging] = useState(false)
  const [backendOk, setBackendOk] = useState<boolean | null>(null)

  // step 2
  const [providerName, setProviderName] = useState('OpenAI')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://api.openai.com/v1')
  const [modelName, setModelName] = useState('gpt-4o-mini')
  const [providerId, setProviderId] = useState<string | null>(null)
  const [savingProvider, setSavingProvider] = useState(false)

  // step 3
  const [transcriberType, setTranscriberType] = useState<string>('groq')
  const [savingTranscriber, setSavingTranscriber] = useState(false)

  function next() {
    setError('')
    setStep(s => s + 1)
  }
  function prev() {
    setError('')
    setStep(s => Math.max(1, s - 1))
  }

  // step 1: ping 后端
  // 关键点：旧实现 useEffect 只在 step===1 时 ping 一次。失败后 backendOk=false 永远卡死，
  // 即便后端随后就绪了也不会刷新。现在改成：
  //   - 手动重试按钮调用 doPing
  //   - Tauri backend-ready / backend-restarted 事件触发 doPing
  //   - 初次失败后 2s 自动再 ping 一次（覆盖 sidecar 慢热场景）
  const doPing = useCallback(async () => {
    setPinging(true)
    const ok = await pingBackend()
    setBackendOk(ok)
    setPinging(false)
    return ok
  }, [])

  useEffect(() => {
    if (step !== 1) return
    let cancelled = false
    let timerId: ReturnType<typeof setTimeout> | null = null
    let offReady: (() => void) | null = null
    let offRestarted: (() => void) | null = null

    ;(async () => {
      const ok = await doPing()
      if (cancelled) return
      if (!ok) {
        // 后端可能正在解压/启动，2s 后再试一次
        timerId = setTimeout(() => { if (!cancelled) doPing() }, 2000)
      }

      // 桌面端订阅 Tauri 事件：后端真正就绪 / 重启完成时立刻再检查一次
      if (isTauri) {
        try {
          const { listen } = await import('@tauri-apps/api/event')
          offReady = await listen('backend-ready', () => { if (!cancelled) doPing() })
          offRestarted = await listen('backend-restarted', () => { if (!cancelled) doPing() })
        }
        catch { /* 拿不到事件 API 不致命 */ }
      }
    })()

    return () => {
      cancelled = true
      if (timerId) clearTimeout(timerId)
      offReady?.()
      offRestarted?.()
    }
  }, [step, doPing])

  async function saveProvider() {
    setError('')
    if (!apiKey.trim()) { setError('请填 API Key'); return }
    if (!baseUrl.trim()) { setError('请填 API 地址'); return }
    if (!providerName.trim()) { setError('请填供应商名'); return }
    if (!modelName.trim()) { setError('请填模型名'); return }
    setSavingProvider(true)
    try {
      const name = providerName.trim()
      let pid: string | undefined

      // 后端 seed_default_providers() 会预置 OpenAI / DeepSeek / Qwen 等同名供应商，
      // 直接 add_provider 撞名会报「供应商名称已存在」。所以：撞名时改为
      // 「找到那个已存在的同名供应商 → 更新它的 key / base_url」而不是新建。
      // 这些调用都带 silent:true —— 撞名是预期内的，不弹全局红 toast。
      try {
        const res: any = await addProvider({
          name,
          api_key: apiKey.trim(),
          base_url: baseUrl.trim(),
          type: 'custom',
          logo: 'custom',
        }, { silent: true })
        pid = (res?.data ?? res) as string | undefined
        if (!pid) throw new Error('后端未返回 provider id')
      }
      catch (addErr: any) {
        const msg = errText(addErr)
        if (!msg.includes('已存在')) throw addErr
        // 撞名：复用已存在的同名供应商
        const list: any[] = (await getProviderList({ silent: true })) || []
        const existing = list.find(p => p?.name === name)
        if (!existing?.id) throw new Error(`供应商「${name}」已存在但无法定位，请换个名字`)
        pid = existing.id
        await updateProviderById({
          id: pid,
          api_key: apiKey.trim(),
          base_url: baseUrl.trim(),
          enabled: 1,
        }, { silent: true })
      }

      setProviderId(pid!)

      // 加一个默认 model（同名 model 已存在时后端会报错，这里也容错）
      try {
        await addModel({ provider_id: pid!, model_name: modelName.trim() }, { silent: true })
      }
      catch (modelErr: any) {
        const msg = errText(modelErr)
        if (!msg.includes('已存在')) throw modelErr
        // 模型已存在，直接继续
      }

      // 测试连通（失败不阻断流程，让用户自己决定继续）
      try { await testConnection({ id: pid!, model: modelName.trim() }, { silent: true }) }
      catch (e: any) {
        console.warn('测试连接失败：', errText(e))
      }
      next()
    }
    catch (e: any) {
      setError(`保存失败：${errText(e)}`)
    }
    finally {
      setSavingProvider(false)
    }
  }

  async function saveTranscriber() {
    setError('')
    setSavingTranscriber(true)
    try {
      // fast-whisper / mlx-whisper 需指定 model size；在线 (groq/bcut/kuaishou) 不用
      const needsSize = transcriberType === 'fast-whisper' || transcriberType === 'mlx-whisper'
      await updateTranscriberConfig({
        transcriber_type: transcriberType,
        ...(needsSize ? { whisper_model_size: 'tiny' } : {}),
      } as any)
      next()
    }
    catch (e: any) {
      setError(`保存失败：${errText(e)}`)
    }
    finally {
      setSavingTranscriber(false)
    }
  }

  function finish() {
    markOnboarded()
    navigate('/', { replace: true })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-pink-50 p-6">
      <div className="w-full max-w-xl rounded-xl border bg-white p-6 shadow-lg">
        <div className="flex items-center gap-3 mb-4">
          <img src={logo} alt="logo" className="h-10 w-10" />
          <div>
            <h1 className="text-xl font-bold">欢迎使用 BiliNote</h1>
            <p className="text-xs text-gray-500">几步配置后就可以开始把视频转笔记。</p>
          </div>
        </div>

        {/* Stepper */}
        <div className="mb-5 flex items-center gap-2 text-xs text-gray-500">
          {[1, 2, 3, 4].map(s => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`flex h-6 w-6 items-center justify-center rounded-full border ${step >= s ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-300 bg-white text-gray-400'}`}
              >{s}</div>
              {s < 4 && <div className={`h-px w-8 ${step > s ? 'bg-blue-600' : 'bg-gray-300'}`} />}
            </div>
          ))}
        </div>

        {step === 1 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">第 1 步 · 后端连通性</h2>
            <p className="text-sm text-gray-600">桌面端会自动启动 Python 后端进程。检查连通中…</p>
            {pinging && <div className="text-sm text-gray-500">检测中…</div>}
            {backendOk === true && <div className="rounded bg-green-50 p-2 text-sm text-green-700">✓ 后端已就绪</div>}
            {backendOk === false && (
              <div className="rounded bg-red-50 p-2 text-sm text-red-700">
                ✗ 暂时连不上后端。可能正在初始化（首次启动会下载依赖），等 1-2 分钟再试。
                右下角的「后端」状态点会持续监控。
              </div>
            )}
            <div className="flex gap-2 justify-end">
              {backendOk !== true && (
                <button
                  className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
                  disabled={pinging}
                  onClick={doPing}
                >
                  {pinging ? '检测中…' : '重新检测'}
                </button>
              )}
              <button className="px-4 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50" disabled={!backendOk} onClick={next}>
                下一步
              </button>
            </div>
          </section>
        )}

        {step === 2 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">第 2 步 · 模型供应商</h2>
            <p className="text-sm text-gray-600">填一个 OpenAI 兼容供应商：DeepSeek / Qwen / Claude / 自托管 / OpenAI 都行。</p>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-600">供应商名（自取）</span>
              <input className="input border rounded px-2 py-1" value={providerName} onChange={e => setProviderName(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-600">API 地址</span>
              <input className="input border rounded px-2 py-1" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-600">API Key</span>
              <input type="password" className="input border rounded px-2 py-1" value={apiKey} onChange={e => setApiKey(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-600">模型名（如 gpt-4o-mini / deepseek-chat / qwen-turbo）</span>
              <input className="input border rounded px-2 py-1" value={modelName} onChange={e => setModelName(e.target.value)} />
            </label>
            {error && <div className="text-xs text-red-600">{error}</div>}
            <div className="flex gap-2 justify-between">
              <button className="text-sm text-gray-500 hover:text-gray-800" onClick={prev}>上一步</button>
              <button className="px-4 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50" disabled={savingProvider} onClick={saveProvider}>
                {savingProvider ? '保存中…' : '保存并下一步'}
              </button>
            </div>
          </section>
        )}

        {step === 3 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">第 3 步 · 音频转写引擎</h2>
            <p className="text-sm text-gray-600">把视频音频转成文字。<strong>推荐在线引擎</strong>，避免本地下载 ~600MB 的模型。</p>
            <div className="grid gap-2">
              {[
                { value: 'groq', title: 'Groq（在线，推荐）', desc: '注册 https://groq.com/ 拿免费 key；速度快、英文语料佳。无需本地模型。' },
                { value: 'bcut', title: '必剪（在线，免登）', desc: '免登，中文表现好；偶尔限流。' },
                { value: 'kuaishou', title: '快手（在线，免登）', desc: '与必剪类似，备选。' },
                { value: 'fast-whisper', title: 'Faster Whisper（本地）', desc: '完全离线但首次需下载 ~75MB（tiny）至 ~3GB（large-v3）的模型。CPU 慢。' },
              ].map(opt => (
                <label key={opt.value} className={`flex gap-3 p-3 rounded border cursor-pointer ${transcriberType === opt.value ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                  <input type="radio" name="transcriber" value={opt.value} checked={transcriberType === opt.value} onChange={e => setTranscriberType(e.target.value)} />
                  <div>
                    <div className="text-sm font-medium">{opt.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
            {error && <div className="text-xs text-red-600">{error}</div>}
            <div className="flex gap-2 justify-between">
              <button className="text-sm text-gray-500 hover:text-gray-800" onClick={prev}>上一步</button>
              <button className="px-4 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50" disabled={savingTranscriber} onClick={saveTranscriber}>
                {savingTranscriber ? '保存中…' : '保存并下一步'}
              </button>
            </div>
          </section>
        )}

        {step === 4 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">第 4 步 · Cookie 同步（可选）</h2>
            <p className="text-sm text-gray-600">
              想总结 <strong>B 站 / 抖音 / 快手</strong> 等需要登录态的平台时，需要把浏览器 cookie 复制到「下载配置」页。
              <br />
              YouTube 一般不需要 cookie。先跳过也没问题，到时再去配。
            </p>
            <div className="rounded bg-gray-50 p-3 text-xs text-gray-600">
              提示：插件版（<a className="text-blue-600 underline" href="https://github.com/JefferyHcool/BiliNote/tree/develop/BillNote_extension" target="_blank" rel="noreferrer">BillNote_extension</a>）支持一键 cookie 同步；桌面版需手动复制。
            </div>
            <div className="flex gap-2 justify-between">
              <button className="text-sm text-gray-500 hover:text-gray-800" onClick={prev}>上一步</button>
              <button className="px-4 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700" onClick={finish}>
                完成，进入 BiliNote
              </button>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

export default Onboarding
