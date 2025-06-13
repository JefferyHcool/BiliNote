// components/LazyImage.tsx
import { useInView } from 'react-intersection-observer'
import { FC, useState } from 'react'
import clsx from 'clsx'

interface LazyImageProps {
    src: string
    alt?: string
    className?: string
    placeholder?: string
}

const LazyImage: FC<LazyImageProps> = ({ src, alt, className, placeholder = '.src/assets/placeholder.png' }) => {
    const { ref, inView } = useInView({ triggerOnce: true, threshold: 0.1 })
    const [loaded, setLoaded] = useState(false)

    return (
        <div ref={ref} className={clsx('overflow-hidden', className)}>
            {inView ? (
                <img
                    src={src}
                    alt={alt}
                    loading="lazy"
                    onLoad={() => setLoaded(true)}
                    className={clsx('transition-opacity duration-300', loaded ? 'opacity-100' : 'opacity-0') +  ' h-10 w-14  rounded-md object-cover'}
                />
            ) : (
                <img src={placeholder} alt="loading" className="opacity-30" />
            )}
        </div>
    )
}

export default LazyImage
