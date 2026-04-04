/**
 * Quick stats card showing project metrics.
 */

interface QuickStatsProps {
  wordCount: number
  targetWords: number
  chapterCount: number
  totalChapters: number
  blueprintCount: number
  costEur?: number
}

export default function QuickStats({
  wordCount,
  targetWords,
  chapterCount,
  totalChapters,
  blueprintCount,
  costEur = 0,
}: QuickStatsProps) {
  const progressPercent = targetWords > 0 ? Math.round((wordCount / targetWords) * 100) : 0

  return (
    <div className="bg-white rounded-xl border p-5">
      <h3 className="font-semibold text-gray-900 mb-4">Statistiken</h3>

      <div className="space-y-4">
        {/* Word count */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">Wörter</span>
            <span className="font-medium">
              {wordCount.toLocaleString()} / {targetWords.toLocaleString()}
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-500 transition-all duration-300"
              style={{ width: `${Math.min(progressPercent, 100)}%` }}
            />
          </div>
          <div className="text-right text-xs text-gray-500 mt-1">
            {progressPercent}%
          </div>
        </div>

        {/* Chapter progress */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-2xl font-bold text-primary-600">
              {chapterCount}
              <span className="text-lg text-gray-400">/{totalChapters || '?'}</span>
            </div>
            <div className="text-xs text-gray-600">Kapitel</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-2xl font-bold text-primary-600">
              {blueprintCount}
              <span className="text-lg text-gray-400">/{totalChapters || '?'}</span>
            </div>
            <div className="text-xs text-gray-600">Blueprints</div>
          </div>
        </div>

        {/* Cost */}
        <div className="pt-3 border-t">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-600">Kosten</span>
            <span className="font-mono text-lg font-medium text-gray-900">
              {costEur.toFixed(2)} EUR
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
