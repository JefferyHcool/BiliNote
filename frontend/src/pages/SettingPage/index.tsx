import SettingLayout from '@/layouts/SettingLayout.tsx'
import Menu from '@/pages/SettingPage/Menu'
import { useProviderStore } from '@/store/providerStore'
import { useEffect } from 'react'

const SettingPage = () => {
  const fetchProviderList = useProviderStore(state => state.fetchProviderList)
  useEffect(() => {
    fetchProviderList()
  }, [])
  return (
    <div className="h-full w-full">
      <SettingLayout Menu={<Menu />} />
    </div>
  )
}
export default SettingPage
