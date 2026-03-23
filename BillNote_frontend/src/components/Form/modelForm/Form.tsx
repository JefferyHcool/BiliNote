import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
  FormDescription,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useParams, useNavigate } from 'react-router-dom'
import { useProviderStore } from '@/store/providerStore'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { testConnection, fetchModels, deleteModelById } from '@/services/model.ts'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx' // ⚡新增 fetchModels
import { ModelSelector } from '@/components/Form/modelForm/ModelSelector.tsx'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.tsx'
import { Tags } from 'lucide-react'
import { X } from 'lucide-react'
import { useModelStore } from '@/store/modelStore'

// ✅ Provider表单schema
const ProviderSchema = z.object({
  name: z.string().min(2, '名称不能少于 2 个字符'),
  apiKey: z.string().optional(),
  baseUrl: z.string().url('必须是合法 URL'),
  type: z.string(),
})

type ProviderFormValues = z.infer<typeof ProviderSchema>

// ✅ Model表单schema
const ModelSchema = z.object({
  modelName: z.string().min(1, '请选择或填写模型名称'),
})

type ModelFormValues = z.infer<typeof ModelSchema>
interface IModel {
  id: string
  created: number
  object: string
  owned_by: string
  permission: string
  root: string
}
const ProviderForm = ({ isCreate = false }: { isCreate?: boolean }) => {
  let { id } = useParams()
  const navigate = useNavigate()
  const isEditMode = !isCreate

  const getProviderById = useProviderStore(state => state.getProviderById)
  const loadProviderById = useProviderStore(state => state.loadProviderById)
  const updateProvider = useProviderStore(state => state.updateProvider)
  const addNewProvider = useProviderStore(state => state.addNewProvider)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [isBuiltIn, setIsBuiltIn] = useState(false)
  const loadModelsById= useModelStore(state => state.loadModelsById)
  const [modelOptions, setModelOptions] = useState<IModel[]>([]) // ⚡新增，保存模型列表
  const [models, setModels]= useState([])
  const [modelLoading, setModelLoading] = useState(false)
  const randomColor = ()=>{
    return '#' + Math.floor(Math.random() * 16777215).toString(16)
  }

  const [search, setSearch] = useState('')
  const providerForm = useForm<ProviderFormValues>({
    resolver: zodResolver(ProviderSchema),
    defaultValues: {
      name: '',
      apiKey: '',
      baseUrl: '',
      type: 'custom',
    },
  })
  const filteredModelOptions = modelOptions.filter(model => {
    const keywords = search.trim().toLowerCase().split(/\s+/) // 支持多个关键词
    const target = model.id.toLowerCase()
    return keywords.every(kw => target.includes(kw))
  })

  const modelForm = useForm<ModelFormValues>({
    resolver: zodResolver(ModelSchema),
    defaultValues: {
      modelName: '',
    },
  })

  useEffect(() => {

    const load = async () => {
      if (isEditMode) {

        const data = await loadProviderById(id!)
        providerForm.reset(data)
        setIsBuiltIn(data.type === 'built-in')
      } else {
        providerForm.reset({
          name: '',
          apiKey: '',
          baseUrl: '',
          type: 'custom',
        })
        setIsBuiltIn(false)
      }
      const models = await loadModelsById(id!)
      if(models){
        console.log('🔧 模型列表:', models)
        setModels(models)

      }
      setLoading(false)
    }
    load()
  }, [id])
  const handelDelete=async (modelId)=>{
    if (!window.confirm('确定要删除这个模型吗？')) return

    try {
      const res = await deleteModelById(modelId)
      console.log('🔧 删除结果:', res)

      toast.success('删除成功')

    } catch (e) {
      toast.error('删除异常')
    }
  }
  // 测试连通性
  const handleTest = async () => {
    const values = providerForm.getValues()
    if (!values.apiKey || !values.baseUrl) {
      toast.error('请填写 API Key 和 Base URL')
      return
    }
    try {
      if (!id){
        toast.error('请先保存供应商信息')
        return
      }
      setTesting(true)
     await testConnection({
             id
          })

        toast.success('测试连通性成功 🎉')

    } catch (error) {

      toast.error(`连接失败: ${data.data.msg || '未知错误'}`)
      // toast.error('测试连通性异常')
    } finally {
      setTesting(false)
    }
  }

  // 加载模型列表
  const handleModelLoad = async () => {
    const values = providerForm.getValues()
    if (!values.apiKey || !values.baseUrl) {
      toast.error('请先填写 API Key 和 Base URL')
      return
    }
    try {
      setModelLoading(true) // ✅ 开始 loading
      const res = await fetchModels(id!, { noCache: true }) // 这里稍后解释
      if (res.data.code === 0 && res.data.data.models.data.length > 0) {
        setModelOptions(res.data.data.models.data)
        console.log('🔧 模型列表:', res.data.data)
        toast.success('模型列表加载成功 🎉')
      } else {
        toast.error('未获取到模型列表')
      }
    } catch (error) {
      toast.error('加载模型列表失败')
    } finally {
      setModelLoading(false) // ✅ 结束 loading
    }
  }

  // 保存Provider信息
  const onProviderSubmit = async (values: ProviderFormValues) => {
    if (isEditMode) {
      await updateProvider({ ...values, id: id! })
      toast.success('更新供应商成功')
    } else {
       id = await addNewProvider({ ...values })

      toast.success('新增供应商成功')
    }
    // 刷新页面

  }

  // 保存Model信息
  const onModelSubmit = async (values: ModelFormValues) => {
    toast.success(`保存模型: ${values.modelName}`)
    await loadModelsById(id!)
  }

  if (loading) return <div className="p-4">加载中...</div>

  return (
    <div className="flex flex-col gap-8 p-4">
      {/* Provider信息表单 */}
      <Form {...providerForm}>
        <form
          onSubmit={providerForm.handleSubmit(onProviderSubmit)}
          className="flex max-w-xl flex-col gap-4"
        >
          <div className="text-lg font-bold">
            {isEditMode ? '编辑模型供应商' : '新增模型供应商'}
          </div>
          {!isBuiltIn && (
            <div className="text-sm text-red-500 italic">
              自定义模型供应商需要确保兼容 OpenAI SDK
            </div>
          )}
          <FormField
            control={providerForm.control}
            name="name"
            render={({ field }) => (
              <FormItem className="flex items-center gap-4">
                <FormLabel className="w-24 text-right">名称</FormLabel>
                <FormControl>
                  <Input {...field} disabled={isBuiltIn} className="flex-1" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={providerForm.control}
            name="apiKey"
            render={({ field }) => (
              <FormItem className="flex items-center gap-4">
                <FormLabel className="w-24 text-right">API Key</FormLabel>
                <FormControl>
                  <Input {...field} className="flex-1" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={providerForm.control}
            name="baseUrl"
            render={({ field }) => (
              <FormItem className="flex items-center gap-4">
                <FormLabel className="w-24 text-right">API地址</FormLabel>
                <FormControl>
                  <Input {...field} className="flex-1" />
                </FormControl>
                <Button type="button" onClick={handleTest} variant="ghost" disabled={testing}>
                  {testing ? '测试中...' : '测试连通性'}
                </Button>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={providerForm.control}
            name="type"
            render={({ field }) => (
              <FormItem className="flex items-center gap-4">
                <FormLabel className="w-24 text-right">类型</FormLabel>
                <FormControl>
                  <Input {...field} disabled className="flex-1" />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="pt-2">
            <Button type="submit" disabled={!providerForm.formState.isDirty}>
              {isEditMode ? '保存修改' : '保存创建'}
            </Button>
          </div>
        </form>
      </Form>

      {/* 模型信息表单 */}
      <div className="flex max-w-xl flex-col gap-4">
        <div className="flex flex-col gap-2">
          <span className="font-bold">模型列表</span>
          <div className={'flex flex-col gap-2 rounded bg-[#FEF0F0] p-2.5'}>
            <h2 className={'font-bold'}>注意!</h2>
            <span>请确保已经保存供应商信息,以及通过测试连通性.</span>
          </div>
          <ModelSelector providerId={id!} />

          {/*<datalist id="model-options">*/}
          {/*  {modelOptions.map(model => (*/}
          {/*    <option key={model.id + '1'} value={model.id} />*/}
          {/*  ))}*/}
          {/*</datalist>*/}
        </div>
        <div className="flex flex-col gap-2">
          <span className="font-bold">已启用模型</span>
          <div className={'flex flex-wrap gap-2 rounded  p-2.5'}>
            {
              models && models.map(model => {
                return (
                  <span key={model.id} className="inline-flex items-center gap-1 rounded-md bg-blue-100 px-2 py-0.5 text-sm text-blue-700">
                    {model.model_name}
                    <button type="button" onClick={() => handelDelete(model.id)} className="hover:text-blue-900">
                      <X className="h-3 w-3" />
                    </button>
                  </span>

                )
              })
            }

          </div>
          {/*<ModelSelector providerId={id!} />*/}

          {/*<datalist id="model-options">*/}
          {/*  {modelOptions.map(model => (*/}
          {/*    <option key={model.id + '1'} value={model.id} />*/}
          {/*  ))}*/}
          {/*</datalist>*/}
        </div>
      </div>
    </div>
  )
}

export default ProviderForm
