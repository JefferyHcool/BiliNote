import { Outlet } from 'react-router-dom'
import Options from '@/components/Form/DownloaderForm/Options.tsx'
import ProxyConfig from '@/components/Form/DownloaderForm/ProxyConfig.tsx'
const Downloader = () => {
  return (
    <div className={'flex h-full min-h-0 flex-col bg-white md:flex-row'}>
      <div
        className={
          'max-h-72 shrink-0 overflow-y-auto border-b border-neutral-200 p-2 md:max-h-none md:w-1/5 md:border-r md:border-b-0'
        }
      >
        <ProxyConfig />
        <Options></Options>
      </div>
      <div className={'min-h-0 flex-1 overflow-y-auto'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Downloader
