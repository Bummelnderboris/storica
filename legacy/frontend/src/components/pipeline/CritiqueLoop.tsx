/**
 * Critique Loop component - shows prose generation critique iterations.
 */

import React from 'react'

interface CritiqueScore {
  category: string
  score: number
  feedback: string
}

interface CritiqueIteration {
  iteration: number
  scores: CritiqueScore[]
  overallScore: number
  passes: boolean
}

interface CritiqueLoopProps {
  iterations: CritiqueIteration[]
  currentIteration: number
  maxIterations: number
  passingThreshold: number
}

export const CritiqueLoop: React.FC<CritiqueLoopProps> = ({
  iterations,
  currentIteration,
  maxIterations,
  passingThreshold
}) => {
  const getScoreColor = (score: number) => {
    if (score >= passingThreshold) return 'text-green-600'
    if (score >= passingThreshold - 1) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-gray-800">Critique Loop</h3>
        <span className="text-sm text-gray-500">
          Iteration {currentIteration} / {maxIterations}
        </span>
      </div>

      {/* Progress bar */}
      <div className="flex gap-1 mb-4">
        {Array.from({ length: maxIterations }).map((_, i) => (
          <div
            key={i}
            className={`h-2 flex-1 rounded-full ${
              i < iterations.length
                ? iterations[i].passes
                  ? 'bg-green-500'
                  : 'bg-yellow-500'
                : i === currentIteration - 1
                ? 'bg-blue-500 animate-pulse'
                : 'bg-gray-200'
            }`}
          />
        ))}
      </div>

      {/* Iteration details */}
      <div className="space-y-3">
        {iterations.map((iteration) => (
          <div
            key={iteration.iteration}
            className={`p-3 rounded-lg ${
              iteration.passes ? 'bg-green-50' : 'bg-yellow-50'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-sm">
                Iteration {iteration.iteration}
              </span>
              <span
                className={`font-bold ${getScoreColor(iteration.overallScore)}`}
              >
                {iteration.overallScore.toFixed(1)} / 10
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {iteration.scores.map((score) => (
                <div key={score.category} className="text-xs">
                  <span className="text-gray-600">{score.category}: </span>
                  <span className={getScoreColor(score.score)}>
                    {score.score.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>

            {iteration.passes && (
              <div className="mt-2 text-xs text-green-600 flex items-center gap-1">
                <span>✓</span>
                <span>Passed threshold ({passingThreshold})</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 flex gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-green-500" />
          Passed
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-yellow-500" />
          Revising
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-blue-500" />
          Current
        </span>
      </div>
    </div>
  )
}

export default CritiqueLoop
