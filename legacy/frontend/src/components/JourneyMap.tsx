/**
 * Visual Journey Map showing project progress through stages.
 */

interface JourneyMapProps {
  currentStage: string
  hasEssence: boolean
  hasArchitecture: boolean
  blueprintCount: number
  chapterCount: number
  totalChapters: number
}

const stages = [
  { id: 'essence', name: 'Essence', icon: '💡' },
  { id: 'architecture', name: 'Architektur', icon: '🏛️' },
  { id: 'blueprint', name: 'Blueprint', icon: '📋' },
  { id: 'prose', name: 'Prosa', icon: '✍️' },
]

export default function JourneyMap({
  currentStage,
  hasEssence,
  hasArchitecture,
  blueprintCount,
  chapterCount,
  totalChapters,
}: JourneyMapProps) {
  const getStageStatus = (stageId: string) => {
    switch (stageId) {
      case 'essence':
        return hasEssence ? 'completed' : currentStage === 'essence' ? 'current' : 'locked'
      case 'architecture':
        return hasArchitecture
          ? 'completed'
          : currentStage === 'architecture'
          ? 'current'
          : 'locked'
      case 'blueprint':
        if (currentStage === 'blueprint') return 'current'
        if (blueprintCount > 0 && blueprintCount >= totalChapters) return 'completed'
        if (blueprintCount > 0) return 'in-progress'
        return hasArchitecture ? 'ready' : 'locked'
      case 'prose':
        if (currentStage === 'prose' || currentStage === 'polish') return 'current'
        if (chapterCount > 0 && chapterCount >= totalChapters) return 'completed'
        if (chapterCount > 0) return 'in-progress'
        return blueprintCount > 0 ? 'ready' : 'locked'
      default:
        return 'locked'
    }
  }

  const getStageProgress = (stageId: string) => {
    switch (stageId) {
      case 'blueprint':
        if (totalChapters === 0) return null
        return `${blueprintCount}/${totalChapters}`
      case 'prose':
        if (totalChapters === 0) return null
        return `${chapterCount}/${totalChapters}`
      default:
        return null
    }
  }

  const getStatusStyles = (status: string) => {
    switch (status) {
      case 'completed':
        return {
          bg: 'bg-green-100',
          border: 'border-green-500',
          icon: 'text-green-600',
          text: 'text-green-700',
        }
      case 'current':
        return {
          bg: 'bg-primary-100',
          border: 'border-primary-500',
          icon: 'text-primary-600',
          text: 'text-primary-700',
          ring: 'ring-4 ring-primary-100',
        }
      case 'in-progress':
        return {
          bg: 'bg-amber-50',
          border: 'border-amber-400',
          icon: 'text-amber-600',
          text: 'text-amber-700',
        }
      case 'ready':
        return {
          bg: 'bg-gray-50',
          border: 'border-gray-300',
          icon: 'text-gray-600',
          text: 'text-gray-700',
        }
      default:
        return {
          bg: 'bg-gray-100',
          border: 'border-gray-200',
          icon: 'text-gray-400',
          text: 'text-gray-400',
        }
    }
  }

  return (
    <div className="py-4">
      <div className="flex items-center justify-between">
        {stages.map((stage, index) => {
          const status = getStageStatus(stage.id)
          const styles = getStatusStyles(status)
          const progress = getStageProgress(stage.id)

          return (
            <div key={stage.id} className="flex items-center">
              {/* Stage node */}
              <div className="flex flex-col items-center">
                <div
                  className={`
                    w-16 h-16 rounded-2xl border-2 flex flex-col items-center justify-center
                    transition-all duration-300
                    ${styles.bg} ${styles.border} ${styles.ring || ''}
                  `}
                >
                  {status === 'completed' ? (
                    <svg
                      className={`w-8 h-8 ${styles.icon}`}
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : status === 'locked' ? (
                    <svg
                      className={`w-6 h-6 ${styles.icon}`}
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    <span className={`text-2xl ${styles.icon}`}>{stage.icon}</span>
                  )}
                  {progress && (
                    <span className={`text-xs font-medium ${styles.text}`}>
                      {progress}
                    </span>
                  )}
                </div>
                <span
                  className={`mt-2 text-sm font-medium ${styles.text}`}
                >
                  {stage.name}
                </span>
              </div>

              {/* Connector */}
              {index < stages.length - 1 && (
                <div className="flex-1 mx-3">
                  <div
                    className={`
                      h-1 rounded-full transition-all duration-300
                      ${
                        getStageStatus(stages[index + 1].id) !== 'locked'
                          ? 'bg-primary-200'
                          : 'bg-gray-200'
                      }
                    `}
                  >
                    {status === 'completed' && (
                      <div className="h-full w-full bg-green-400 rounded-full" />
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
