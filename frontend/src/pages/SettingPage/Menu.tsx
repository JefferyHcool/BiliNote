import {
  BotMessageSquare,
  SquareChevronRight,
  Captions,
  HardDriveDownload,
  Wrench,
  Info,
} from 'lucide-react'
import MenuBar, { IMenuProps } from '@/pages/SettingPage/components/menuBar.tsx'

const Menu = () => {
  const menuList: IMenuProps[] = [
    {
      id: 'model',
      name: 'AI 模型设置',
      icon: <BotMessageSquare />,
      path: '/settings/model',
    },
    // TODO ：下一版本升级优化
    // {
    //   id: ' transcriber',
    //   name: '音频转译配置',
    //   icon: <Captions />,
    //   path: '/settings/transcriber',
    // },
    // //下载配置
    {
      id: 'download',
      name: '下载配置',
      icon: <HardDriveDownload />,
      path: '/settings/download',
    },
    // //其他配置
    // {
    //   id: 'prompt',
    //   name: '提示词设置',
    //   icon: <SquareChevronRight />,
    //   path: '/settings/prompt',
    // },
    {
      id: 'about',
      name: '关于',
      icon: <Info />,
      path: '/settings/about',
    },
    // {
    //   id: 'other',
    //   name: '其他配置',
    //   icon: <Wrench />,
    //   path: '/settings/other',
    // },
  ]
  return (
    <div className="flex h-full flex-col">
      <div className={'flex w-full flex-col gap-2'}>
        <div className="text-2xl font-medium">设置</div>
        <div className="text-sm font-light text-gray-800">全局配置与模型设置</div>
      </div>
      <div className="mt-6 flex-1">
        {menuList &&
          menuList.map(item => {
            return <MenuBar key={item.id} menuItem={item} />
          })}
      </div>
    </div>
  )
}
export default Menu
