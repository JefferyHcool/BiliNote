import { Outlet } from 'react-router-dom'
import Options from '@/components/Form/DownloaderForm/Options.tsx'
import ProxyConfig from '@/components/Form/DownloaderForm/ProxyConfig.tsx'
const Downloader = () => {
  return (
    <div className={'flex h-full bg-card'}>
      <div className={'flex flex-1/5 flex-col gap-3 overflow-y-auto border-r border-border p-2'}>
        <ProxyConfig />
        <Options></Options>
      </div>
      <div className={'flex-4/5'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Downloader
