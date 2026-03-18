import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi, generationApi } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import StageProgress from '../components/StageProgress'
import ProgressBar from '../components/ProgressBar'
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
  const queryClient = useQueryClient()

  const [activeTab, setActiveTab] = useState<ContentTab>('overview')
  const [activeTask, setActiveTask] = useState<GenerationTask | null>(null)
  const [showApproval, setShowApproval] = useState(false)
  const [progress, setProgress] = useState<{ percent: number; message: string } | null>(null)

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

  // WebSocket for real-time updates
  const handleProgress = useCallback((data: {
    task_id: number
    status: string
    message: string
    progress_percent: number
  }) => {
    setProgress({ percent: data.progress_percent, message: data.message })

    if (data.status === 'awaiting_approval') {
      // Fetch the task to get result
      generationApi.getTask(data.task_id).then((response) => {
        setActiveTask(response.data)
        setShowApproval(true)
        setProgress(null)
      })
    }
  }, [])

  const handleCompleted = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
    setProgress(null)
    setShowApproval(false)
  }, [queryClient, projectId])

  const handleError = useCallback((data: { error: string }) => {
    setProgress(null)
    alert(`Generation failed: ${data.error}`)
  }, [])

  useWebSocket({
    projectId,
    onProgress: handleProgress,
    onCompleted: handleCompleted,
    onError: handleError,
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
          ? { label: 'Generate Essence', action: () => generateEssence.mutate() }
          : { label: 'Generate Architecture', action: () => generateArchitecture.mutate() }
      case 'architecture':
        return { label: 'Generate Architecture', action: () => generateArchitecture.mutate() }
      case 'blueprint':
        const nextBlueprint = project.content_summary.blueprint_count + 1
        if (nextBlueprint <= project.total_chapters) {
          return {
            label: `Generate Blueprint ${nextBlueprint}`,
            action: () => generateBlueprint.mutate({ chapterNum: nextBlueprint }),
          }
        }
        return {
          label: 'Start Writing Chapters',
          action: () => generateChapter.mutate({ chapterNum: 1 }),
        }
      case 'prose':
        const nextChapter = project.current_chapter + 1
        if (nextChapter <= project.total_chapters) {
          return {
            label: `Generate Chapter ${nextChapter}`,
            action: () => generateChapter.mutate({ chapterNum: nextChapter }),
          }
        }
        return { label: 'Novel Complete!', action: () => {} }
      default:
        return null
    }
  }

  const nextAction = getNextAction()

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
        <p className="text-gray-600 mt-1">
          Author style: {project.author_id} | Target: {project.target_words.toLocaleString()} words
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <StageProgress currentStage={project.current_stage} />
      </div>

      {progress && (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <ProgressBar
            progress={progress.percent}
            message={progress.message}
            status="running"
          />
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm border mb-6">
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
            <div className="space-y-6">
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-primary-600">
                    {project.content_summary.total_word_count.toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-600">Words Written</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-primary-600">
                    {project.content_summary.chapter_count} / {project.total_chapters}
                  </div>
                  <div className="text-sm text-gray-600">Chapters Complete</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-primary-600">
                    {Math.round(
                      (project.content_summary.total_word_count / project.target_words) * 100
                    )}
                    %
                  </div>
                  <div className="text-sm text-gray-600">Progress</div>
                </div>
              </div>

              {project.seed && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Story Seed</h3>
                  <p className="text-gray-600 bg-gray-50 rounded-lg p-4">{project.seed}</p>
                </div>
              )}

              {nextAction && nextAction.label !== 'Novel Complete!' && (
                <div className="flex justify-center">
                  <button
                    onClick={nextAction.action}
                    disabled={!!progress}
                    className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 font-medium"
                  >
                    {nextAction.label}
                  </button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'essence' && (
            essence ? (
              <ContentViewer content={essence.content} />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No essence generated yet.</p>
                <button
                  onClick={() => generateEssence.mutate()}
                  disabled={!!progress}
                  className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  Generate Essence
                </button>
              </div>
            )
          )}

          {activeTab === 'architecture' && (
            architecture ? (
              <ContentViewer content={architecture.content} />
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No architecture generated yet.</p>
                {project.content_summary.has_essence && (
                  <button
                    onClick={() => generateArchitecture.mutate()}
                    disabled={!!progress}
                    className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
                  >
                    Generate Architecture
                  </button>
                )}
              </div>
            )
          )}

          {activeTab === 'blueprints' && (
            <div className="text-center py-8 text-gray-500">
              <p>Blueprints: {project.content_summary.blueprint_count} generated</p>
            </div>
          )}

          {activeTab === 'chapters' && (
            chapters?.chapters?.length > 0 ? (
              <div className="space-y-4">
                {chapters.chapters.map((chapter: { chapter_num: number; word_count: number; content: string }) => (
                  <div key={chapter.chapter_num} className="border rounded-lg p-4">
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="font-medium">Chapter {chapter.chapter_num}</h3>
                      <span className="text-sm text-gray-500">
                        {chapter.word_count.toLocaleString()} words
                      </span>
                    </div>
                    <p className="text-gray-600 text-sm line-clamp-3">
                      {chapter.content.substring(0, 300)}...
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No chapters written yet.</p>
              </div>
            )
          )}
        </div>
      </div>

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
            activeTask.chapter_num ? ` - Chapter ${activeTask.chapter_num}` : ''
          }`}
          isLoading={approveTask.isPending || regenerateTask.isPending}
        />
      )}
    </div>
  )
}
