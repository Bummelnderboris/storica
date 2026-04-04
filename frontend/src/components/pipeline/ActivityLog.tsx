/**
 * Activity Log component for real-time pipeline visualization.
 */

import { useEffect, useRef, useState } from 'react'
import { LogEntry as LogEntryType, VerbosityLevel } from './types'
import LogEntry from './LogEntry'
import VerbositySelector from './VerbositySelector'
import CostTracker from './CostTracker'

interface ActivityLogProps {
  logs: LogEntryType[]
  isRunning: boolean
  currentStep?: string
  progress?: number
  totalCost: number
  costLimit?: number
  isPaused?: boolean
  onContinue?: () => void
  onStop?: () => void
  onClear?: () => void
  onDownload?: () => void
}

export default function ActivityLog({
  logs,
  isRunning,
  currentStep,
  progress = 0,
  totalCost,
  costLimit = 3.0,
  isPaused = false,
  onContinue,
  onStop,
  onClear,
  onDownload,
}: ActivityLogProps) {
  const [verbosity, setVerbosity] = useState<VerbosityLevel>('normal')
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new logs come in
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  // Detect manual scroll
  const handleScroll = () => {
    if (!logContainerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50
    setAutoScroll(isAtBottom)
  }

  return (
    <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {isRunning ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                <span className="text-sm font-medium text-green-700">Live</span>
              </>
            ) : (
              <span className="text-sm font-medium text-gray-500">Inaktiv</span>
            )}
          </div>

          {isRunning && currentStep && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">{currentStep}</span>
              <span className="text-sm font-medium text-primary-600">{progress}%</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <VerbositySelector value={verbosity} onChange={setVerbosity} />

          <div className="flex items-center gap-1 border-l pl-3">
            {onDownload && (
              <button
                onClick={onDownload}
                className="p-1.5 text-gray-500 hover:text-gray-700 rounded"
                title="Log herunterladen"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </button>
            )}
            {onClear && (
              <button
                onClick={onClear}
                className="p-1.5 text-gray-500 hover:text-gray-700 rounded"
                title="Log leeren"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress bar */}
      {isRunning && (
        <div className="h-1 bg-gray-100">
          <div
            className="h-full bg-primary-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Log entries */}
      <div
        ref={logContainerRef}
        onScroll={handleScroll}
        className="max-h-80 overflow-y-auto p-3 space-y-1 font-mono text-sm bg-gray-900 text-gray-100"
        style={{ minHeight: '200px' }}
      >
        {logs.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            Keine Aktivitäten
          </div>
        ) : (
          logs.map((log) => (
            <LogEntry key={log.id} entry={log} verbosity={verbosity} />
          ))
        )}

        {/* Auto-scroll indicator */}
        {!autoScroll && logs.length > 0 && (
          <button
            onClick={() => {
              setAutoScroll(true)
              if (logContainerRef.current) {
                logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
              }
            }}
            className="sticky bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 bg-primary-600 text-white text-xs rounded-full shadow-lg hover:bg-primary-700"
          >
            ↓ Neue Einträge
          </button>
        )}
      </div>

      {/* Cost tracker */}
      <div className="p-4 border-t">
        <CostTracker
          currentCost={totalCost}
          limit={costLimit}
          isPaused={isPaused}
          onContinue={onContinue}
          onStop={onStop}
        />
      </div>
    </div>
  )
}
