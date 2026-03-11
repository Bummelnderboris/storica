const stages = [
  { id: 'essence', label: 'Essence' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'blueprint', label: 'Blueprints' },
  { id: 'prose', label: 'Prose' },
  { id: 'polish', label: 'Polish' },
  { id: 'complete', label: 'Complete' },
]

interface StageProgressProps {
  currentStage: string
}

export default function StageProgress({ currentStage }: StageProgressProps) {
  const currentIndex = stages.findIndex((s) => s.id === currentStage)

  return (
    <div className="flex items-center justify-between">
      {stages.map((stage, index) => {
        const isCompleted = index < currentIndex
        const isCurrent = index === currentIndex
        const isUpcoming = index > currentIndex

        return (
          <div key={stage.id} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  isCompleted
                    ? 'bg-green-500 text-white'
                    : isCurrent
                    ? 'bg-primary-500 text-white'
                    : 'bg-gray-200 text-gray-500'
                }`}
              >
                {isCompleted ? (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  index + 1
                )}
              </div>
              <span
                className={`mt-1 text-xs ${
                  isUpcoming ? 'text-gray-400' : 'text-gray-700'
                }`}
              >
                {stage.label}
              </span>
            </div>
            {index < stages.length - 1 && (
              <div
                className={`h-0.5 w-12 mx-2 ${
                  index < currentIndex ? 'bg-green-500' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
