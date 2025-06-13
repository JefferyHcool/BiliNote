import { FC } from 'react'
import Lottie from 'lottie-react'
import Animation from '@/assets/Lottie/404.json'

const NotFound: FC = () => {
  return (
    <div className="flex items-center justify-center">
      <Lottie animationData={Animation} loop autoplay />
    </div>
  )
}

export default NotFound
