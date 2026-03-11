import { useEffect, useRef, useCallback, useState } from 'react'
import { useAuthStore } from '../store/auth'

interface WebSocketMessage {
  type: string
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
}

export function useWebSocket({
  projectId,
  onMessage,
  onProgress,
  onContentReady,
  onCompleted,
  onError,
  onCostUpdate,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const accessToken = useAuthStore((state) => state.accessToken)

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

        switch (message.type) {
          case 'generation.progress':
            onProgress?.(message as unknown as Parameters<NonNullable<typeof onProgress>>[0])
            break
          case 'generation.content_ready':
            onContentReady?.(message as unknown as Parameters<NonNullable<typeof onContentReady>>[0])
            break
          case 'generation.completed':
            onCompleted?.(message as unknown as Parameters<NonNullable<typeof onCompleted>>[0])
            break
          case 'generation.error':
            onError?.(message as unknown as Parameters<NonNullable<typeof onError>>[0])
            break
          case 'cost.update':
            onCostUpdate?.(message as unknown as Parameters<NonNullable<typeof onCostUpdate>>[0])
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
