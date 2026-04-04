/**
 * Zustand store for Pipeline state management.
 */

import { create } from 'zustand'

export interface PhaseOutput {
  phase_name: string
  status: string
  output?: Record<string, unknown>
  error?: string
  input_tokens: number
  output_tokens: number
  execution_time_ms: number
}

export interface Phase {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'awaiting_approval'
  output?: Record<string, unknown>
  error?: string
  startedAt?: string
  completedAt?: string
}

export interface CritiqueIteration {
  iteration: number
  scores: { category: string; score: number; feedback: string }[]
  overallScore: number
  passes: boolean
}

export interface PendingApproval {
  phase: string
  preview: Record<string, unknown>
}

export interface PipelineState {
  // Status
  status: string
  projectId: number | null
  authorId: string | null
  isRunning: boolean
  error: string | null

  // Progress
  phases: PhaseOutput[]
  currentPhase: string | null
  progress: number
  currentChapter: number
  totalChapters: number

  // Critique loop
  critiqueIterations: CritiqueIteration[]
  currentIteration: number

  // Cost
  inputTokens: number
  outputTokens: number
  estimatedCost: number

  // Pending approval
  pendingApproval: PendingApproval | null

  // Actions
  setStatus: (status: string) => void
  setPhases: (phases: PhaseOutput[]) => void
  setCurrentPhase: (phase: string | null) => void
  setProgress: (progress: number) => void
  setIsRunning: (isRunning: boolean) => void
  setError: (error: string | null) => void
  setPendingApproval: (approval: PendingApproval | null) => void
  setChapterProgress: (current: number, total: number) => void
  addCritiqueIteration: (iteration: CritiqueIteration) => void
  updateCost: (inputTokens: number, outputTokens: number) => void
  startPipeline: (projectId: number, authorId: string) => void
  reset: () => void
}

const initialState = {
  status: 'idle',
  projectId: null,
  authorId: null,
  isRunning: false,
  error: null,
  phases: [],
  currentPhase: null,
  progress: 0,
  currentChapter: 0,
  totalChapters: 0,
  critiqueIterations: [],
  currentIteration: 0,
  inputTokens: 0,
  outputTokens: 0,
  estimatedCost: 0,
  pendingApproval: null,
}

export const usePipelineStore = create<PipelineState>((set) => ({
  ...initialState,

  setStatus: (status) => set({ status }),

  setPhases: (phases) => set({ phases }),

  setCurrentPhase: (currentPhase) => set({ currentPhase }),

  setProgress: (progress) => set({ progress }),

  setIsRunning: (isRunning) => set({ isRunning }),

  setError: (error) => set({ error }),

  setPendingApproval: (pendingApproval) => set({ pendingApproval }),

  setChapterProgress: (current, total) =>
    set({
      currentChapter: current,
      totalChapters: total,
    }),

  addCritiqueIteration: (iteration) =>
    set((state) => ({
      critiqueIterations: [...state.critiqueIterations, iteration],
      currentIteration: iteration.iteration,
    })),

  updateCost: (inputTokens, outputTokens) =>
    set((state) => {
      const newInput = state.inputTokens + inputTokens
      const newOutput = state.outputTokens + outputTokens
      // Approximate cost calculation (Claude Sonnet pricing)
      const cost = (newInput / 1000) * 0.003 + (newOutput / 1000) * 0.015
      return {
        inputTokens: newInput,
        outputTokens: newOutput,
        estimatedCost: Math.round(cost * 10000) / 10000,
      }
    }),

  startPipeline: (projectId, authorId) =>
    set({
      status: 'running',
      projectId,
      authorId,
      isRunning: true,
      phases: [],
      critiqueIterations: [],
      inputTokens: 0,
      outputTokens: 0,
      estimatedCost: 0,
      error: null,
    }),

  reset: () => set(initialState),
}))
