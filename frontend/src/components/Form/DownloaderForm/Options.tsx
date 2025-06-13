import ProviderCard from '@/components/Form/DownloaderForm/providerCard.tsx'
import { Button } from '@/components/ui/button.tsx'
import { useProviderStore } from '@/store/providerStore'
import { useNavigate } from 'react-router-dom'
import { DouyinLogo, KuaishouLogo } from '@/components/Icons/platform.tsx'
import { videoPlatforms } from '@/constant/note.ts'

const Provider = () => {
  const navigate = useNavigate()
  const handleClick = () => {
    navigate(`/settings/model/new`)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-light">下载器配置</div>
      <div>
        {videoPlatforms &&
          videoPlatforms.map((provider, index) => {
            if (provider.value !== 'local')
              return (
                <ProviderCard
                  key={index}
                  providerName={provider.label}
                  Icon={provider?.logo}
                  id={provider.value}
                />
              )
          })}
      </div>
    </div>
  )
}
export default Provider
