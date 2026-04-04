/**
 * Types for pipeline visualization.
 */

export type LogEntryType =
  | 'step'
  | 'thinking'
  | 'artifact'
  | 'decision'
  | 'cost'
  | 'warning'
  | 'error'
  | 'progress'
  | 'completed'

export interface LogEntry {
  id: string
  timestamp: Date
  type: LogEntryType
  taskId?: number
  data: LogEntryData
}

export interface LogEntryData {
  // Common
  message?: string

  // Step
  progress_percent?: number

  // Thinking
  thought?: string

  // Artifact
  name?: string
  artifact_type?: string
  preview?: string
  has_full_content?: boolean

  // Decision
  decision?: string
  reasoning?: string

  // Cost
  input_tokens?: number
  output_tokens?: number
  cost_eur?: number
  total_cost_eur?: number

  // Warning
  action_required?: boolean

  // Error
  error?: string
  recoverable?: boolean

  // Completed
  next_stage?: string
}

export type VerbosityLevel = 'minimal' | 'normal' | 'detailed'

export interface PipelineState {
  isRunning: boolean
  currentStep: string
  progress: number
  totalCost: number
  logs: LogEntry[]
  verbosity: VerbosityLevel
  isPaused: boolean
}
