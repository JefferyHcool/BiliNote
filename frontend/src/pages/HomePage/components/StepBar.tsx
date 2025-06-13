import { FC } from 'react'

interface Step {
  label: string
  key: string
  Icon?: React.ReactNode // 加一个可选的 Lottie 动画
}

interface StepBarProps {
  steps: Step[]
  currentStep: string
}

const StepBar: FC<StepBarProps> = ({ steps, currentStep }) => {
  const currentIndex = steps.findIndex(step => step.key === currentStep)

  return (
    <div className="flex w-full items-center justify-between">
      {steps.map((step, index) => {
        const isActive = index <= currentIndex
        const isCurrent = index === currentIndex
        const isLast = index === steps.length - 1
        return (
          <div key={step.key} className="relative flex flex-1 flex-col items-center">
            {/* 圆圈或者Lottie */}
            <div className="relative flex flex-col items-center justify-center">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                  isActive ? 'bg-primary text-white' : 'bg-gray-300 text-gray-600'
                }`}
              >
                {index + 1}
              </div>
              {/* 当前步骤显示动画 */}
              {isCurrent && step.Icon && (
                <div className="absolute top-10 h-16 w-16">{step.Icon}</div>
              )}
            </div>

            {/* 步骤名称 */}
            <div className="mt-4 text-center text-xs text-gray-700">{step.label}</div>

            {/* 连接线 */}

            <div className={`h-1 w-full ${isActive ? 'bg-primary' : 'bg-gray-300'}`}></div>
          </div>
        )
      })}
    </div>
  )
}

export default StepBar
