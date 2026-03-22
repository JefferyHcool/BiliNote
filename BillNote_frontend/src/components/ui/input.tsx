import * as React from 'react'

import { cn } from '@/lib/utils'

type InputProps = React.ComponentProps<'input'> & {
  clearable?: boolean
  onClear?: () => void
}

function Input({ className, type, value, onChange, clearable = false, onClear, disabled, ...props }: InputProps) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const hasValue = value !== undefined && value !== null && `${value}`.length > 0
  const showClear = clearable && !disabled && hasValue

  const handleClear = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    event.stopPropagation()

    if (onChange) {
      const nextEvent = {
        target: { value: '' },
        currentTarget: { value: '' },
      } as React.ChangeEvent<HTMLInputElement>
      onChange(nextEvent)
    }

    inputRef.current?.focus()
    onClear?.()

  }

  return (
    <div className="relative w-full">
      <input
        ref={inputRef}
        type={type}
        data-slot="input"
        className={cn(
          'file:text-foreground placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground dark:bg-input/30 border-input flex h-9 w-full min-w-0 rounded-md border bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
          'focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]',
          'aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive',
          clearable && 'pr-9',
          className
        )}
        value={value ?? ''}
        onChange={onChange}
        disabled={disabled}
        {...props}
      />
      {showClear && (
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground absolute right-2 top-1/2 -translate-y-1/2"
          aria-label="清空输入"
          onClick={handleClear}
        >
          ×
        </button>
      )}
    </div>
  )
}

export { Input }
