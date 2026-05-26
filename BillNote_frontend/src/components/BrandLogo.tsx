import { Link } from 'react-router-dom'
import logo from '@/assets/icon.svg'

interface BrandLogoProps {
  to?: string
}

export function BrandLogo({ to = '/' }: BrandLogoProps) {
  return (
    <Link to={to} className="flex items-center gap-2">
      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-2xl">
        <img src={logo} alt="logo" className="h-full w-full object-contain" />
      </div>
      <div className="text-2xl font-bold text-gray-800">BiliNote</div>
    </Link>
  )
}
