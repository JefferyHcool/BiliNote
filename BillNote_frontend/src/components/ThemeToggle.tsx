import { Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip.tsx'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="relative text-muted-foreground hover:text-primary cursor-pointer rounded p-1 hover:bg-accent transition-colors"
          >
            <Sun className="h-5 w-5 scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
            <Moon className="absolute h-5 w-5 scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
            <span className="sr-only">切换主题</span>
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <span>{theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
