import { Switch } from '@/components/ui/switch'
import { FC } from 'react'
import styles from './index.module.css'
import { useNavigate, useParams } from 'react-router-dom'
import AILogo from '@/components/Form/modelForm/Icons'
import { useProviderStore } from '@/store/providerStore'

export interface IProviderCardProps {
  id: string
  providerName: string
  Icon: string
  enable: number
}

const ProviderCard: FC<IProviderCardProps> = ({
  providerName,
  Icon,
  id,
}: IProviderCardProps) => {
  const navigate = useNavigate()
  const updateProvider = useProviderStore(state => state.updateProvider)
  const enabled = useProviderStore(state => state.provider.find(p => p.id === id)?.enabled)

  const isChecked = enabled === 1

  const handleToggle = (checked: boolean) => {
    const allProviders = useProviderStore.getState().provider
    const provider = allProviders.find(p => p.id === id)
    if (!provider) return
    updateProvider({
      ...provider,
      enabled: checked ? 1 : 0,
    })
  }

  // @ts-ignore
  const { id: currentId } = useParams()
  const isActive = currentId === id

  return (
    <div
      className={
        styles.card +
        ' flex h-14 cursor-pointer items-center justify-between rounded border border-[#f3f3f3] p-2' +
        (isActive ? ' bg-[#F0F0F0] font-semibold text-blue-600' : '')
      }
      // 整行可点跳转到对应供应商编辑页（之前 onClick 只挂在 icon+名字那一小块 div 上，
      // 名字和开关之间的空白区域点不动）
      onClick={() => navigate(`/settings/model/${id}`)}
    >
      <div className="flex items-center text-lg">
        <div className="flex h-9 w-9 items-center">
          <AILogo name={Icon} />
        </div>
        <div className="font-semibold">{providerName}</div>
      </div>

      {/* Switch 自己的点击不应该冒泡触发整行跳转 */}
      <div onClick={e => e.stopPropagation()}>
        <Switch
          checked={isChecked}
          onCheckedChange={handleToggle}
        />
      </div>
    </div>
  )
}
export default ProviderCard
