import Provider from '@/components/Form/modelForm/Provider.tsx'
import { Outlet } from 'react-router-dom'

const Model = () => {
  return (
    <div className={'flex h-full min-h-0 bg-card'}>
      <div className={'flex-1/5 min-h-0 overflow-y-auto border-r border-border p-2'}>
        <Provider></Provider>
      </div>
      <div className={'flex-4/5 min-h-0 overflow-y-auto'}>
        <Outlet />
      </div>
    </div>
  )
}
export default Model
