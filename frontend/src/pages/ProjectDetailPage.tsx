/**
 * Project Detail Page with new dashboard design.
 */

import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi, generationApi } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { LogEntry } from '../components/pipeline/types'
import { ActivityLog } from '../components/pipeline'
import JourneyMap from '../components/JourneyMap'
import QuickStats from '../components/QuickStats'
import ContentViewer from '../components/ContentViewer'
import ApprovalModal from '../components/ApprovalModal'

interface ProjectDetail {
  id: number
  name: string
  author_id: string
  target_words: number
  current_stage: string
  current_chapter: number
  total_chapters: number
  seed: string | null
  content_summary: {
    has_essence: boolean
    has_architecture: boolean
    has_story_bible: boolean
    blueprint_count: number
    chapter_count: number
    total_word_count: number
  }
  created_at: string
  updated_at: string
}

interface GenerationTask {
  id: number
  task_type: string
  chapter_num: number | null
  status: string
  progress_percent: number
  progress_message: string | null
  result_preview: string | null
  error_message: string | null
}

type ContentTab = 'overview' | 'essence' | 'architecture' | 'blueprints' | 'chapters'

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const projectId = parseInt(id!)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState<ContentTab>('overview')
  const [activeTask, setActiveTask] = useState<GenerationTask | null>(null)
  const [showApproval, setShowApproval] = useState(false)
  const [progress, setProgress] = useState<{ percent: number; message: string } | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [totalCost, setTotalCost] = useState(0)
  const [isPaused, setIsPaused] = useState(false)

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const response = await projectsApi.get(projectId)
      return response.data as ProjectDetail
    },
  })

  const { data: essence } = useQuery({
    queryKey: ['project', projectId, 'essence'],
    queryFn: async () => {
      const response = await projectsApi.getEssence(projectId)
      return response.data
    },
    enabled: project?.content_summary.has_essence,
  })

  const { data: architecture } = useQuery({
    queryKey: ['project', projectId, 'architecture'],
    queryFn: async () => {
      const response = await projectsApi.getArchitecture(projectId)
      return response.data
    },
    enabled: project?.content_summary.has_architecture,
  })

  const { data: chapters } = useQuery({
    queryKey: ['project', projectId, 'chapters'],
    queryFn: async () => {
      const response = await projectsApi.getChapters(projectId)
      return response.data
    },
    enabled: (project?.content_summary.chapter_count ?? 0) > 0,
  })

  // WebSocket handlers
  const handleProgress = useCallback(
    (data: {
      task_id: number
      status: string
      message: string
      progress_percent: number
    }) => {
      setProgress({ percent: data.progress_percent, message: data.message })

      if (data.status === 'awaiting_approval') {
        generationApi.getTask(data.task_id).then((response) => {
          setActiveTask(response.data)
          setShowApproval(true)
          setProgress(null)
        })
      }
    },
    []
  )

  const handleCompleted = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    setProgress(null)
    setShowApproval(false)
  }, [queryClient, projectId])

  const handleError = useCallback((data: { error: string }) => {
    setProgress(null)
    alert(`Generation failed: ${data.error}`)
  }, [])

  const handleLogEntry = useCallback((entry: LogEntry) => {
    setLogs((prev) => [...prev.slice(-99), entry]) // Keep last 100 entries

    // Update cost from cost entries
    if (entry.type === 'cost' && entry.data.total_cost_eur !== undefined) {
      setTotalCost(entry.data.total_cost_eur)
    }

    // Check for pause warnings
    if (entry.type === 'warning' && entry.data.action_required) {
      setIsPaused(true)
    }
  }, [])

  const { isConnected } = useWebSocket({
    projectId,
    onProgress: handleProgress,
    onCompleted: handleCompleted,
    onError: handleError,
    onLogEntry: handleLogEntry,
  })

  // Generation mutations
  const generateEssence = useMutation({
    mutationFn: (guidance?: string) => generationApi.generateEssence(projectId, guidance),
    onSuccess: (response) => {
      setActiveTask(response.data)
      setProgress({ percent: 0, message: 'Starting generation...' })
    },
  })

  const generateArchitecture = useMutation({
    mutationFn: (guidance?: string) => generationApi.generateArchitecture(projectId, guidance),
    onSuccess: (response) => {
      setActiveTask(response.data)
      setProgress({ percent: 0, message: 'Starting generation...' })
    },
  })

  const generateBlueprint = useMutation({
    mutationFn: ({ chapterNum, guidance }: { chapterNum: number; guidance?: string }) =>
      generationApi.generateBlueprint(projectId, chapterNum, guidance),
    onSuccess: (response) => {
      setActiveTask(response.data)
      setProgress({ percent: 0, message: 'Starting generation...' })
    },
  })

  const generateChapter = useMutation({
    mutationFn: ({ chapterNum, guidance }: { chapterNum: number; guidance?: string }) =>
      generationApi.generateChapter(projectId, chapterNum, guidance),
    onSuccess: (response) => {
      setActiveTask(response.data)
      setProgress({ percent: 0, message: 'Starting generation...' })
    },
  })

  const approveTask = useMutation({
    mutationFn: (taskId: number) => generationApi.approveTask(taskId, true),
    onSuccess: () => {
      setShowApproval(false)
      setActiveTask(null)
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })

  const regenerateTask = useMutation({
    mutationFn: ({ taskId, guidance }: { taskId: number; guidance: string }) =>
      generationApi.regenerateTask(taskId, guidance),
    onSuccess: (response) => {
      setActiveTask(response.data)
      setShowApproval(false)
      setProgress({ percent: 0, message: 'Regenerating...' })
    },
  })

  const handleClearLogs = () => setLogs([])

  const handleDownloadLogs = () => {
    const content = logs
      .map(
        (log) =>
          `[${log.timestamp.toISOString()}] [${log.type.toUpperCase()}] ${JSON.stringify(log.data)}`
      )
      .join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `storica-log-${projectId}-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!project) {
    return <div className="text-center text-red-600">Project not found</div>
  }

  const getNextAction = () => {
    switch (project.current_stage) {
      case 'essence':
        return !project.content_summary.has_essence
          ? { label: 'Essence generieren', action: () => generateEssence.mutate() }
          : { label: 'Architektur generieren', action: () => generateArchitecture.mutate() }
      case 'architecture':
        return { label: 'Architektur generieren', action: () => generateArchitecture.mutate() }
      case 'blueprint':
        const nextBlueprint = project.content_summary.blueprint_count + 1
        if (nextBlueprint <= project.total_chapters) {
          return {
            label: `Blueprint ${nextBlueprint} generieren`,
            action: () => generateBlueprint.mutate({ chapterNum: nextBlueprint }),
          }
        }
        return {
          label: 'Kapitel 1 schreiben',
          action: () => generateChapter.mutate({ chapterNum: 1 }),
        }
      case 'prose':
        const nextChapter = project.current_chapter + 1
        if (nextChapter <= project.total_chapters) {
          return {
            label: `Kapitel ${nextChapter} schreiben`,
            action: () => generateChapter.mutate({ chapterNum: nextChapter }),
          }
        }
        return { label: 'Roman fertig!', action: () => {} }
      default:
        return null
    }
  }

  const nextAction = getNextAction()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          <p className="text-gray-600 mt-1">
            Autor: {project.author_id} | Ziel: {project.target_words.toLocaleString()} Wörter
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isConnected && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Verbunden
            </span>
          )}
          <button
            onClick={() => navigate(`/projects/${projectId}/bible`)}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 border rounded-lg hover:bg-gray-50"
          >
            Story Bible
          </button>
        </div>
      </div>

      {/* Journey Map */}
      <div className="bg-white rounded-xl border p-6">
        <JourneyMap
          currentStage={project.current_stage}
          hasEssence={project.content_summary.has_essence}
          hasArchitecture={project.content_summary.has_architecture}
          blueprintCount={project.content_summary.blueprint_count}
          chapterCount={project.content_summary.chapter_count}
          totalChapters={project.total_chapters}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Stats */}
        <div className="space-y-6">
          <QuickStats
            wordCount={project.content_summary.total_word_count}
            targetWords={project.target_words}
            chapterCount={project.content_summary.chapter_count}
            totalChapters={project.total_chapters}
            blueprintCount={project.content_summary.blueprint_count}
            costEur={totalCost}
          />

          {/* Next action */}
          {nextAction && nextAction.label !== 'Roman fertig!' && (
            <div className="bg-primary-50 rounded-xl border border-primary-100 p-5">
              <h3 className="font-semibold text-primary-900 mb-3">Nächster Schritt</h3>
              <button
                onClick={nextAction.action}
                disabled={!!progress}
                className="w-full px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 font-medium"
              >
                {nextAction.label}
              </button>
            </div>
          )}
        </div>

        {/* Right column - Activity Log */}
        <div className="lg:col-span-2">
          <ActivityLog
            logs={logs}
            isRunning={!!progress}
            currentStep={progress?.message}
            progress={progress?.percent}
            totalCost={totalCost}
            isPaused={isPaused}
            onClear={handleClearLogs}
            onDownload={handleDownloadLogs}
            onContinue={() => setIsPaused(false)}
            onStop={() => setIsPaused(false)}
          />
        </div>
      </div>

      {/* Content tabs */}
      <div className="bg-white rounded-xl border">
        <div className="border-b">
          <nav className="flex -mb-px">
            {(['overview', 'essence', 'architecture', 'blueprints', 'chapters'] as const).map(
              (tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-3 text-sm font-medium border-b-2 ${
                    activeTab === tab
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              )
            )}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'overview' && (
            <div className="space-y-4">
              {project.seed && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Story Seed</h3>
                  <div className="bg-gray-50 rounded-lg p-4 text-gray-700 whitespace-pre-wrap">
                    {project.seed}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'essence' &&
            (essence ? (
              <ContentViewer content={essence.content} />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>Keine Essence generiert.</p>
                <button
                  onClick={() => generateEssence.mutate()}
                  disabled={!!progress}
                  className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  Essence generieren
                </button>
              </div>
            ))}

          {activeTab === 'architecture' &&
            (architecture ? (
              <ContentViewer content={architecture.content} />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>Keine Architektur generiert.</p>
                {project.content_summary.has_essence && (
                  <button
                    onClick={() => generateArchitecture.mutate()}
                    disabled={!!progress}
                    className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
                  >
                    Architektur generieren
                  </button>
                )}
              </div>
            ))}

          {activeTab === 'blueprints' && (
            <div className="text-center py-8 text-gray-500">
              <p>Blueprints: {project.content_summary.blueprint_count} generiert</p>
            </div>
          )}

          {activeTab === 'chapters' &&
            (chapters?.chapters?.length > 0 ? (
              <div className="space-y-4">
                {chapters.chapters.map(
                  (chapter: { chapter_num: number; word_count: number; content: string }) => (
                    <div key={chapter.chapter_num} className="border rounded-lg p-4">
                      <div className="flex justify-between items-center mb-2">
                        <h3 className="font-medium">Kapitel {chapter.chapter_num}</h3>
                        <span className="text-sm text-gray-500">
                          {chapter.word_count.toLocaleString()} Wörter
                        </span>
                      </div>
                      <p className="text-gray-600 text-sm line-clamp-3">
                        {chapter.content.substring(0, 300)}...
                      </p>
                    </div>
                  )
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>Noch keine Kapitel geschrieben.</p>
              </div>
            ))}
        </div>
      </div>

      {/* Approval Modal */}
      {showApproval && activeTask?.result_preview && (
        <ApprovalModal
          isOpen={showApproval}
          onClose={() => setShowApproval(false)}
          onApprove={() => approveTask.mutate(activeTask.id)}
          onRegenerate={(guidance) =>
            regenerateTask.mutate({ taskId: activeTask.id, guidance })
          }
          content={activeTask.result_preview}
          title={`Review ${activeTask.task_type}${
            activeTask.chapter_num ? ` - Kapitel ${activeTask.chapter_num}` : ''
          }`}
          isLoading={approveTask.isPending || regenerateTask.isPending}
        />
      )}
    </div>
  )
}
