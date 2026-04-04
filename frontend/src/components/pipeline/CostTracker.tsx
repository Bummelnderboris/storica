/**
 * Cost tracker component showing current costs and limits.
 */

interface CostTrackerProps {
  currentCost: number
  limit?: number
  warningThreshold?: number
  onContinue?: () => void
  onStop?: () => void
  isPaused?: boolean
}

export default function CostTracker({
  currentCost,
  limit = 3.0,
  warningThreshold = 2.5,
  onContinue,
  onStop,
  isPaused = false,
}: CostTrackerProps) {
  const percentage = Math.min((currentCost / limit) * 100, 100)
  const isWarning = currentCost >= warningThreshold
  const isLimit = currentCost >= limit

  const getProgressColor = () => {
    if (isLimit) return 'bg-red-500'
    if (isWarning) return 'bg-orange-500'
    return 'bg-primary-500'
  }

  return (
    <div
      className={`
        rounded-lg border p-4 transition-all
        ${isLimit ? 'bg-red-50 border-red-200' : isWarning ? 'bg-orange-50 border-orange-200' : 'bg-gray-50 border-gray-200'}
      `}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">Kosten</span>
        <span
          className={`
            text-lg font-bold
            ${isLimit ? 'text-red-600' : isWarning ? 'text-orange-600' : 'text-gray-900'}
          `}
        >
          {currentCost.toFixed(2)} / {limit.toFixed(2)} EUR
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ${getProgressColor()}`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Warning message */}
      {isWarning && !isLimit && (
        <div className="mt-3 flex items-center gap-2 text-orange-700 text-sm">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          <span>Kostenlimit fast erreicht!</span>
        </div>
      )}

      {/* Limit reached - action required */}
      {(isLimit || isPaused) && (
        <div className="mt-3 space-y-3">
          <div className="flex items-center gap-2 text-red-700 text-sm">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <span>Generierung pausiert - Kostenlimit erreicht</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onContinue}
              className="flex-1 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
            >
              Weitermachen (+1 EUR)
            </button>
            <button
              onClick={onStop}
              className="px-4 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300 transition-colors"
            >
              Stoppen
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
