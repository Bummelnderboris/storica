import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { usePipelineStore } from '../store/pipeline'
import { pipelineApi } from '../services/api'
import PhaseProgress from '../components/pipeline/PhaseProgress'
import PhaseApproval from '../components/pipeline/PhaseApproval'
import AgentThinking from '../components/pipeline/AgentThinking'
import CritiqueLoop from '../components/pipeline/CritiqueLoop'

export default function PipelinePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const projectId = id ? parseInt(id, 10) : 0

  const {
    status,
    currentPhase,
    phases,
    progress,
    pendingApproval,
    isRunning,
    error,
    critiqueIterations,
    currentIteration,
    setStatus,
    setPhases,
    setProgress,
    setPendingApproval,
    setIsRunning,
    setError,
    reset,
  } = usePipelineStore()

  useEffect(() => {
    if (!projectId) return

    const fetchStatus = async () => {
      try {
        const response = await pipelineApi.getStatus(projectId)
        const data = response.data
        setStatus(data.status)
        setPhases(data.phases || [])
        setProgress(data.progress_percent || 0)
        setIsRunning(data.status === 'running')

        // Check for pending approvals
        if (data.status === 'awaiting_approval' && data.current_phase) {
          const previewResponse = await pipelineApi.getPhasePreview(
            projectId,
            data.current_phase
          )
          setPendingApproval({
            phase: data.current_phase,
            preview: previewResponse.data,
          })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch pipeline status')
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 3000) // Poll every 3 seconds

    return () => {
      clearInterval(interval)
      reset()
    }
  }, [projectId])

  const handleStart = async (authorId: string, autoApprove: boolean = false) => {
    try {
      setIsRunning(true)
      setError(null)
      await pipelineApi.start(projectId, authorId, autoApprove)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline')
      setIsRunning(false)
    }
  }

  const handlePause = async () => {
    try {
      await pipelineApi.pause(projectId)
      setIsRunning(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause pipeline')
    }
  }

  const handleResume = async () => {
    try {
      await pipelineApi.resume(projectId)
      setIsRunning(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume pipeline')
    }
  }

  const handleApprove = async (phase: string) => {
    try {
      await pipelineApi.approvePhase(projectId, phase)
      setPendingApproval(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve phase')
    }
  }

  const handleReject = async (phase: string, reason: string) => {
    try {
      await pipelineApi.rejectPhase(projectId, phase, reason)
      setPendingApproval(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject phase')
    }
  }

  if (!projectId) {
    return (
      <div className="p-8">
        <p className="text-red-500">Invalid project ID</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <button
              onClick={() => navigate(`/projects/${projectId}`)}
              className="text-sm text-gray-500 hover:text-gray-700 mb-2"
            >
              &larr; Back to Project
            </button>
            <h1 className="text-3xl font-bold text-gray-900">Generation Pipeline</h1>
            <p className="text-gray-600 mt-1">
              Status: <span className="font-medium capitalize">{status}</span>
            </p>
          </div>

          <div className="flex gap-3">
            {!isRunning && status !== 'completed' && (
              <button
                onClick={() => handleStart('duerrenmatt', false)}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Start Pipeline
              </button>
            )}
            {isRunning && (
              <button
                onClick={handlePause}
                className="px-6 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
              >
                Pause
              </button>
            )}
            {status === 'paused' && (
              <button
                onClick={handleResume}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Resume
              </button>
            )}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Progress Section */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
          <PhaseProgress
            phases={phases}
            currentPhase={currentPhase}
            progress={progress}
          />
        </div>

        {/* Agent Thinking Display */}
        {isRunning && currentPhase && (
          <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
            <AgentThinking
              agentName={currentPhase.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              isStreaming={isRunning}
            />
          </div>
        )}

        {/* Critique Loop Display */}
        {currentPhase === 'prose_generation' && critiqueIterations.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
            <CritiqueLoop
              iterations={critiqueIterations}
              currentIteration={currentIteration}
              maxIterations={3}
              passingThreshold={7.0}
            />
          </div>
        )}

        {/* Approval Modal */}
        {pendingApproval && (
          <PhaseApproval
            phase={pendingApproval.phase}
            phaseName={pendingApproval.phase.replace(/_/g, ' ')}
            outputPreview={pendingApproval.preview}
            onApprove={() => handleApprove(pendingApproval.phase)}
            onReject={(reason) => handleReject(pendingApproval.phase, reason)}
            onClose={() => setPendingApproval(null)}
          />
        )}

        {/* Phase Details */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Phase Results</h2>
          {phases.length === 0 ? (
            <p className="text-gray-500">No phases completed yet.</p>
          ) : (
            <div className="space-y-4">
              {phases.map((phase, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg border ${
                    phase.status === 'completed'
                      ? 'border-green-200 bg-green-50'
                      : phase.status === 'failed'
                      ? 'border-red-200 bg-red-50'
                      : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium capitalize">
                      {phase.phase_name.replace(/_/g, ' ')}
                    </h3>
                    <span
                      className={`text-sm px-2 py-1 rounded ${
                        phase.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : phase.status === 'failed'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {phase.status}
                    </span>
                  </div>
                  {phase.execution_time_ms > 0 && (
                    <p className="text-sm text-gray-500 mt-1">
                      Execution time: {(phase.execution_time_ms / 1000).toFixed(2)}s
                    </p>
                  )}
                  {phase.error && (
                    <p className="text-sm text-red-600 mt-2">{phase.error}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
