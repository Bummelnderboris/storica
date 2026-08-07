/**
 * Phase Progress component - shows progress through pipeline phases.
 */

import React from 'react'

interface PhaseOutput {
  phase_name: string
  status: string
  output?: Record<string, unknown>
  error?: string
  input_tokens?: number
  output_tokens?: number
  execution_time_ms?: number
}

interface PhaseProgressProps {
  phases: PhaseOutput[]
  currentPhase?: string | null
  progress?: number
}

const statusIcons: Record<string, string> = {
  pending: '○',
  running: '◐',
  completed: '●',
  failed: '✕',
  awaiting_approval: '◑'
}

const statusColors: Record<string, string> = {
  pending: 'text-gray-400',
  running: 'text-blue-500 animate-pulse',
  completed: 'text-green-500',
  failed: 'text-red-500',
  awaiting_approval: 'text-yellow-500'
}

export const PhaseProgress: React.FC<PhaseProgressProps> = ({
  phases,
  currentPhase,
  progress = 0
}) => {
  // If no phases yet, show default pipeline phases
  const defaultPhases: PhaseOutput[] = [
    { phase_name: 'author_loading', status: 'pending' },
    { phase_name: 'topic_exploration', status: 'pending' },
    { phase_name: 'thesis_development', status: 'pending' },
    { phase_name: 'character_derivation', status: 'pending' },
    { phase_name: 'story_architecture', status: 'pending' },
    { phase_name: 'prose_generation', status: 'pending' },
    { phase_name: 'consistency_check', status: 'pending' }
  ]

  const displayPhases = phases.length > 0 ? phases : defaultPhases

  const formatPhaseName = (name: string) => {
    return name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  return (
    <div className="w-full">
      {/* Progress bar */}
      {progress > 0 && (
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-500 mb-1">
            <span>Progress</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Phase indicators */}
      <div className="flex items-center justify-between">
        {displayPhases.map((phase, index) => (
          <React.Fragment key={phase.phase_name}>
            {/* Phase indicator */}
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-lg ${
                  statusColors[phase.status] || statusColors.pending
                } ${phase.phase_name === currentPhase ? 'ring-2 ring-blue-400' : ''}`}
              >
                {statusIcons[phase.status] || statusIcons.pending}
              </div>
              <span className="text-xs mt-1 text-gray-600 max-w-[80px] text-center truncate">
                {formatPhaseName(phase.phase_name)}
              </span>
              {phase.execution_time_ms && phase.execution_time_ms > 0 && (
                <span className="text-xs text-gray-400">
                  {Math.round(phase.execution_time_ms / 1000)}s
                </span>
              )}
            </div>

            {/* Connector line */}
            {index < displayPhases.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-2 ${
                  displayPhases[index + 1]?.status !== 'pending'
                    ? 'bg-green-500'
                    : 'bg-gray-200'
                }`}
              />
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

export default PhaseProgress
