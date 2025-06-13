import { FC } from 'react'
import Lottie from 'lottie-react'
import loadingJson from '@/assets/Lottie/idle.json'

const Idle: FC = () => {
  return (
    <div className="flex items-center justify-center">
      <Lottie animationData={loadingJson} loop autoplay style={{ width: 350, height: 350 }} />
    </div>
  )
}

export default Idle
