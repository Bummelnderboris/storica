/**
 * Individual log entry component.
 */

import { useState } from 'react'
import { LogEntry as LogEntryType, VerbosityLevel } from './types'

interface LogEntryProps {
  entry: LogEntryType
  verbosity: VerbosityLevel
}

const typeConfig: Record<string, { icon: string; label: string; color: string }> = {
  step: { icon: '▶️', label: 'SCHRITT', color: 'text-blue-600 bg-blue-50' },
  thinking: { icon: '💭', label: 'DENKEN', color: 'text-purple-600 bg-purple-50' },
  artifact: { icon: '📄', label: 'ARTEFAKT', color: 'text-green-600 bg-green-50' },
  decision: { icon: '⚖️', label: 'ENTSCHEIDUNG', color: 'text-amber-600 bg-amber-50' },
  cost: { icon: '💰', label: 'KOSTEN', color: 'text-gray-600 bg-gray-50' },
  warning: { icon: '⚠️', label: 'WARNUNG', color: 'text-orange-600 bg-orange-50' },
  error: { icon: '❌', label: 'FEHLER', color: 'text-red-600 bg-red-50' },
  progress: { icon: '⏳', label: 'FORTSCHRITT', color: 'text-blue-600 bg-blue-50' },
  completed: { icon: '✅', label: 'FERTIG', color: 'text-green-600 bg-green-50' },
}

export default function LogEntry({ entry, verbosity }: LogEntryProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const config = typeConfig[entry.type] || typeConfig.step

  // Filter by verbosity
  if (verbosity === 'minimal') {
    if (!['step', 'warning', 'error', 'completed'].includes(entry.type)) {
      return null
    }
    if (entry.type === 'cost' && entry.data.cost_eur === undefined) {
      return null
    }
  }

  if (verbosity === 'normal') {
    if (entry.type === 'thinking') {
      return null
    }
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const renderContent = () => {
    switch (entry.type) {
      case 'step':
      case 'progress':
        return (
          <div className="flex items-center gap-2">
            <span>{entry.data.message}</span>
            {entry.data.progress_percent !== undefined && (
              <span className="text-sm text-gray-500">
                {entry.data.progress_percent}%
              </span>
            )}
          </div>
        )

      case 'thinking':
        return (
          <div className="text-sm italic text-gray-600">
            {entry.data.thought}
          </div>
        )

      case 'artifact':
        return (
          <div>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-2 text-sm hover:underline"
            >
              <span className="font-medium">{entry.data.name}</span>
              <span className="text-xs text-gray-500">
                ({entry.data.artifact_type})
              </span>
              <svg
                className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
            {isExpanded && entry.data.preview && (
              <div className="mt-2 p-3 bg-white rounded border text-sm text-gray-700 whitespace-pre-wrap">
                {entry.data.preview}
                {entry.data.has_full_content && (
                  <span className="text-gray-400">...</span>
                )}
              </div>
            )}
          </div>
        )

      case 'decision':
        return (
          <div>
            <div className="font-medium">{entry.data.decision}</div>
            {entry.data.reasoning && (
              <div className="text-sm text-gray-600 mt-1">
                {entry.data.reasoning}
              </div>
            )}
          </div>
        )

      case 'cost':
        return (
          <div className="flex items-center gap-3 text-sm">
            <span>
              +{entry.data.cost_eur?.toFixed(3)} EUR
            </span>
            <span className="text-gray-500">
              (Total: {entry.data.total_cost_eur?.toFixed(2)} EUR)
            </span>
            {entry.data.input_tokens && (
              <span className="text-xs text-gray-400">
                {entry.data.input_tokens.toLocaleString()} in / {entry.data.output_tokens?.toLocaleString()} out
              </span>
            )}
          </div>
        )

      case 'warning':
        return (
          <div className="font-medium">
            {entry.data.message}
            {entry.data.action_required && (
              <span className="ml-2 text-xs px-2 py-0.5 bg-orange-100 rounded">
                Aktion erforderlich
              </span>
            )}
          </div>
        )

      case 'error':
        return (
          <div>
            <div className="font-medium">{entry.data.error}</div>
            {entry.data.recoverable !== undefined && (
              <span className="text-xs text-gray-500">
                {entry.data.recoverable ? 'Wiederherstellbar' : 'Kritisch'}
              </span>
            )}
          </div>
        )

      case 'completed':
        return (
          <div className="font-medium">
            Generation abgeschlossen
            {entry.data.next_stage && (
              <span className="text-sm text-gray-600 ml-2">
                → Nächste Phase: {entry.data.next_stage}
              </span>
            )}
          </div>
        )

      default:
        return <span>{JSON.stringify(entry.data)}</span>
    }
  }

  return (
    <div
      className={`
        flex gap-3 py-2 px-3 rounded-lg text-sm animate-slideIn
        ${config.color}
      `}
    >
      <span className="text-gray-400 font-mono text-xs whitespace-nowrap">
        {formatTime(entry.timestamp)}
      </span>
      <span className="text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
        [{config.label}]
      </span>
      <div className="flex-1 min-w-0">{renderContent()}</div>
    </div>
  )
}
