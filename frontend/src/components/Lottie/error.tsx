import { FC } from 'react'
import Lottie from 'lottie-react'
import error from '@/assets/Lottie/Error.json'

const Error: FC = () => {
  return (
    <div className="flex items-center justify-center">
      <Lottie
        animationData={error}
        loop
        autoplay
        style={{
          width: 450,
          height: 450,
        }}
      />
    </div>
  )
}

export default Error
