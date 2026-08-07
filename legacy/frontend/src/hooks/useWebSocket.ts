import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '../store/auth'
import { LogEntry, LogEntryType } from '../components/pipeline/types'

interface WebSocketMessage {
  type: string
  task_id?: number
  timestamp?: string
  [key: string]: unknown
}

interface UseWebSocketOptions {
  projectId: number
  onMessage?: (message: WebSocketMessage) => void
  onProgress?: (data: {
    task_id: number
    status: string
    message: string
    progress_percent: number
  }) => void
  onContentReady?: (data: {
    task_id: number
    content_preview: string
    word_count: number
  }) => void
  onCompleted?: (data: { task_id: number; next_stage: string | null }) => void
  onError?: (data: { task_id: number; error: string; recoverable: boolean }) => void
  onCostUpdate?: (data: { session_tokens: number; session_cost_usd: number }) => void
  onLogEntry?: (entry: LogEntry) => void
}

let logIdCounter = 0
const generateLogId = () => `log-${Date.now()}-${logIdCounter++}`

export function useWebSocket({
  projectId,
  onMessage,
  onProgress,
  onContentReady,
  onCompleted,
  onError,
  onCostUpdate,
  onLogEntry,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const accessToken = useAuthStore((state) => state.accessToken)

  const createLogEntry = useCallback(
    (type: LogEntryType, data: LogEntry['data'], taskId?: number): LogEntry => {
      return {
        id: generateLogId(),
        timestamp: new Date(),
        type,
        taskId,
        data,
      }
    },
    []
  )

  const connect = useCallback(() => {
    if (!accessToken || !projectId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${projectId}?token=${accessToken}`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setIsConnected(true)
      setReconnectAttempts(0)
    }

    ws.onclose = () => {
      setIsConnected(false)

      // Attempt reconnection with exponential backoff
      if (reconnectAttempts < 5) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
        setTimeout(() => {
          setReconnectAttempts((prev) => prev + 1)
          connect()
        }, delay)
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        onMessage?.(message)

        const taskId = message.task_id

        switch (message.type) {
          // Legacy generation messages
          case 'generation.progress':
            onProgress?.(message as unknown as Parameters<NonNullable<typeof onProgress>>[0])
            onLogEntry?.(
              createLogEntry(
                'progress',
                {
                  message: message.message as string,
                  progress_percent: message.progress_percent as number,
                },
                taskId
              )
            )
            break

          case 'generation.content_ready':
            onContentReady?.(message as unknown as Parameters<NonNullable<typeof onContentReady>>[0])
            onLogEntry?.(
              createLogEntry(
                'artifact',
                {
                  name: 'Content Ready',
                  artifact_type: 'content',
                  preview: message.content_preview as string,
                },
                taskId
              )
            )
            break

          case 'generation.completed':
            onCompleted?.(message as unknown as Parameters<NonNullable<typeof onCompleted>>[0])
            onLogEntry?.(
              createLogEntry(
                'completed',
                { next_stage: message.next_stage as string | undefined },
                taskId
              )
            )
            break

          case 'generation.error':
            onError?.(message as unknown as Parameters<NonNullable<typeof onError>>[0])
            onLogEntry?.(
              createLogEntry(
                'error',
                {
                  error: message.error as string,
                  recoverable: message.recoverable as boolean,
                },
                taskId
              )
            )
            break

          case 'cost.update':
            onCostUpdate?.(message as unknown as Parameters<NonNullable<typeof onCostUpdate>>[0])
            break

          // New pipeline messages
          case 'pipeline.step':
            onLogEntry?.(
              createLogEntry(
                'step',
                {
                  message: message.message as string,
                  progress_percent: message.progress_percent as number,
                },
                taskId
              )
            )
            break

          case 'pipeline.thinking':
            onLogEntry?.(
              createLogEntry(
                'thinking',
                { thought: message.thought as string },
                taskId
              )
            )
            break

          case 'pipeline.artifact':
            onLogEntry?.(
              createLogEntry(
                'artifact',
                {
                  name: message.name as string,
                  artifact_type: message.artifact_type as string,
                  preview: message.preview as string,
                  has_full_content: message.has_full_content as boolean,
                },
                taskId
              )
            )
            break

          case 'pipeline.decision':
            onLogEntry?.(
              createLogEntry(
                'decision',
                {
                  decision: message.decision as string,
                  reasoning: message.reasoning as string,
                },
                taskId
              )
            )
            break

          case 'pipeline.cost':
            onLogEntry?.(
              createLogEntry(
                'cost',
                {
                  input_tokens: message.input_tokens as number,
                  output_tokens: message.output_tokens as number,
                  cost_eur: message.cost_eur as number,
                  total_cost_eur: message.total_cost_eur as number,
                },
                taskId
              )
            )
            break

          case 'pipeline.warning':
            onLogEntry?.(
              createLogEntry(
                'warning',
                {
                  message: message.message as string,
                  action_required: message.action_required as boolean,
                },
                taskId
              )
            )
            break
        }
      } catch {
        // Ignore parse errors
      }
    }

    wsRef.current = ws
  }, [
    accessToken,
    projectId,
    reconnectAttempts,
    onMessage,
    onProgress,
    onContentReady,
    onCompleted,
    onError,
    onCostUpdate,
    onLogEntry,
    createLogEntry,
  ])

  useEffect(() => {
    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  // Keep-alive ping
  useEffect(() => {
    if (!isConnected) return

    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => clearInterval(interval)
  }, [isConnected])

  return { isConnected }
}
