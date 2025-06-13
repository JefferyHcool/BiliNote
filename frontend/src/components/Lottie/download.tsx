import { FC, useRef, useEffect } from 'react'
import Lottie, { LottieRefCurrentProps } from 'lottie-react'
import download from '@/assets/Lottie/download.json'

interface LoadingProps {
  play?: boolean // 是否播放
  color?: string // 控制主色，比如 "#00BFFF"
}

const Downloading: FC<LoadingProps> = ({ play = true, color = '#00BFFF' }) => {
  const lottieRef = useRef<LottieRefCurrentProps>(null)

  useEffect(() => {
    if (!lottieRef.current) return

    if (play) {
      lottieRef.current.play()
    } else {
      lottieRef.current.pause()
    }
  }, [play])

  return (
    <div className="flex items-center justify-center">
      <Lottie
        lottieRef={lottieRef}
        animationData={download}
        loop
        autoplay={play}
        style={{
          width: 150,
          height: 150,
          filter: `drop-shadow(0 0 4px ${color}) saturate(2) brightness(1.2)`,
        }}
      />
    </div>
  )
}

export default Downloading
