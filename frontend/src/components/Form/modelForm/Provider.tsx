import ProviderCard from '@/components/Form/modelForm/components/providerCard.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useProviderStore } from '@/store/providerStore'
import { useNavigate } from 'react-router-dom'

const Provider = () => {
  const providers = useProviderStore(state => state.provider)
  const navigate = useNavigate()
  const handleClick = () => {
    navigate(`/settings/model/new`)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className={'search flex gap-1 py-1.5'}>
        <Button
          type={'button'}
          onClick={() => {
            handleClick()
          }}
          className="w-full"
        >
          添加模型供应商
        </Button>
      </div>
      <div className="text-sm font-light">模型供应商列表</div>
      <div>
        {providers &&
          providers.map((provider, index) => {
            return (
              <ProviderCard
                key={index}
                providerName={provider.name}
                Icon={provider.logo}
                id={provider.id}
                enable={provider.enabled}
              />
            )
          })}
      </div>
    </div>
  )
}
export default Provider
