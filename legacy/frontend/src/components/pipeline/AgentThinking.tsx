/**
 * Agent Thinking component - shows agent reasoning in real-time.
 */

import React, { useEffect, useState } from 'react'

interface AgentThinkingProps {
  agentName: string
  thinkingText?: string
  isStreaming?: boolean
}

export const AgentThinking: React.FC<AgentThinkingProps> = ({
  agentName,
  thinkingText,
  isStreaming = false
}) => {
  const [dots, setDots] = useState('.')

  // Animate dots while streaming
  useEffect(() => {
    if (!isStreaming) return

    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '.' : prev + '.'))
    }, 500)

    return () => clearInterval(interval)
  }, [isStreaming])

  return (
    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
        <span className="font-medium text-gray-700">{agentName}</span>
        {isStreaming && (
          <span className="text-gray-400 text-sm">thinking{dots}</span>
        )}
      </div>

      {thinkingText && (
        <div className="text-sm text-gray-600 font-mono bg-white p-3 rounded border max-h-48 overflow-y-auto">
          <p className="whitespace-pre-wrap">{thinkingText}</p>
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-0.5" />
          )}
        </div>
      )}
    </div>
  )
}

export default AgentThinking
