import { ComponentType, FC } from 'react'
import styles from './index.module.css'
import { useNavigate, useParams } from 'react-router-dom'

export interface IProviderCardProps {
  id: string
  providerName: string
  Icon: ComponentType
}
const ProviderCard: FC<IProviderCardProps> = ({ providerName, Icon, id }: IProviderCardProps) => {
  const navigate = useNavigate()
  const handleClick = () => {
    navigate(`/settings/download/${id}`)
  }

  // @ts-expect-error useParams may return incomplete type
  const { id: currentId } = useParams()
  const isActive = currentId === id
  return (
    <div
      onClick={() => {
        handleClick()
      }}
      className={
        styles.card +
        ' flex h-14 items-center justify-between rounded border border-[#f3f3f3] p-2' +
        (isActive ? ' bg-[#F0F0F0] font-semibold text-blue-600' : '')
      }
    >
      <div className="flex items-center gap-2 text-lg">
        <div className="flex h-6 w-6 items-center">{<Icon></Icon>}</div>
        <div className="font-semibold">{providerName}</div>
      </div>
    </div>
  )
}
export default ProviderCard
