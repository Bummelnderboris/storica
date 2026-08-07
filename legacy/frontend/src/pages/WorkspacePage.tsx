/**
 * Writing Workspace Page - Split-pane editor with blueprint and AI assistance.
 */

import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi, generationApi } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import ContentViewer from '../components/ContentViewer'

interface Blueprint {
  id: number
  chapter_num: number
  content: string
  version: number
}

interface Chapter {
  id: number
  chapter_num: number
  content: string
  word_count: number
  version: number
}

export default function WorkspacePage() {
  const { id, chapterNum } = useParams<{ id: string; chapterNum: string }>()
  const projectId = parseInt(id!)
  const currentChapter = parseInt(chapterNum || '1')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState<{ percent: number; message: string } | null>(null)
  const [showBlueprint, setShowBlueprint] = useState(true)
  const [guidance, setGuidance] = useState('')

  // Fetch project data
  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const response = await projectsApi.get(projectId)
      return response.data
    },
  })

  // Fetch blueprint for current chapter
  const { data: blueprint } = useQuery({
    queryKey: ['project', projectId, 'blueprint', currentChapter],
    queryFn: async () => {
      const response = await projectsApi.getBlueprint(projectId, currentChapter)
      return response.data as Blueprint
    },
  })

  // Fetch chapter content
  const { data: chapter } = useQuery({
    queryKey: ['project', projectId, 'chapter', currentChapter],
    queryFn: async () => {
      const response = await projectsApi.getChapter(projectId, currentChapter)
      return response.data as Chapter
    },
  })

  // WebSocket for progress updates
  const handleProgress = useCallback(
    (data: { progress_percent: number; message: string; status: string }) => {
      setProgress({ percent: data.progress_percent, message: data.message })
      if (data.status === 'awaiting_approval' || data.status === 'completed') {
        setIsGenerating(false)
        setProgress(null)
        queryClient.invalidateQueries({
          queryKey: ['project', projectId, 'chapter', currentChapter],
        })
      }
    },
    [queryClient, projectId, currentChapter]
  )

  const handleError = useCallback(() => {
    setIsGenerating(false)
    setProgress(null)
  }, [])

  useWebSocket({
    projectId,
    onProgress: handleProgress,
    onError: handleError,
  })

  // Generate chapter mutation
  const generateChapter = useMutation({
    mutationFn: () =>
      generationApi.generateChapter(projectId, currentChapter, guidance || undefined),
    onSuccess: () => {
      setIsGenerating(true)
      setGuidance('')
    },
  })

  // Navigation
  const goToChapter = (num: number) => {
    navigate(`/projects/${projectId}/workspace/${num}`)
  }

  const totalChapters = project?.total_chapters || 0

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <div>
            <h1 className="text-lg font-bold text-gray-900">
              Kapitel {currentChapter}
              {blueprint?.content && (
                <span className="ml-2 text-sm font-normal text-gray-500">
                  {/* Extract title from blueprint if available */}
                </span>
              )}
            </h1>
            <p className="text-sm text-gray-600">{project?.name}</p>
          </div>
        </div>

        {/* Chapter navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => goToChapter(currentChapter - 1)}
            disabled={currentChapter <= 1}
            className="p-2 text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <span className="text-sm text-gray-600">
            {currentChapter} / {totalChapters}
          </span>
          <button
            onClick={() => goToChapter(currentChapter + 1)}
            disabled={currentChapter >= totalChapters}
            className="p-2 text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBlueprint(!showBlueprint)}
            className={`
              px-3 py-1.5 text-sm rounded-lg transition-colors
              ${showBlueprint ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600'}
            `}
          >
            📋 Blueprint
          </button>
        </div>
      </div>

      {/* Main workspace */}
      <div className="flex-1 flex gap-4 pt-4 overflow-hidden">
        {/* Blueprint panel */}
        {showBlueprint && (
          <div className="w-1/3 flex flex-col bg-white rounded-xl border overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50">
              <h2 className="font-semibold text-gray-900">Blueprint</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {blueprint ? (
                <ContentViewer content={blueprint.content} />
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <p>Kein Blueprint für dieses Kapitel.</p>
                  <button
                    onClick={() => {
                      generationApi.generateBlueprint(projectId, currentChapter)
                    }}
                    className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm"
                  >
                    Blueprint generieren
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Editor panel */}
        <div
          className={`flex-1 flex flex-col bg-white rounded-xl border overflow-hidden ${
            showBlueprint ? '' : 'w-full'
          }`}
        >
          <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Kapiteltext</h2>
            {chapter && (
              <span className="text-sm text-gray-500">
                {chapter.word_count.toLocaleString()} Wörter
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {isGenerating ? (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mb-4"></div>
                <p className="text-gray-600">{progress?.message || 'Generiere...'}</p>
                {progress && (
                  <div className="w-48 h-2 bg-gray-200 rounded-full mt-4">
                    <div
                      className="h-full bg-primary-500 rounded-full transition-all"
                      style={{ width: `${progress.percent}%` }}
                    />
                  </div>
                )}
              </div>
            ) : chapter ? (
              <div className="p-6 prose prose-lg max-w-none">
                <ContentViewer content={chapter.content} />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full p-6">
                <div className="text-center max-w-md">
                  <div className="text-4xl mb-4">✍️</div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Kapitel noch nicht geschrieben
                  </h3>
                  <p className="text-gray-600 mb-6">
                    {blueprint
                      ? 'Das Blueprint ist bereit. Starte die Generierung mit optionaler Anleitung.'
                      : 'Generiere zuerst ein Blueprint für dieses Kapitel.'}
                  </p>

                  {blueprint && (
                    <>
                      <textarea
                        value={guidance}
                        onChange={(e) => setGuidance(e.target.value)}
                        placeholder="Optionale Anleitung für die KI... (z.B. Fokus auf Dialog, mehr Action, etc.)"
                        rows={3}
                        className="w-full px-4 py-3 border rounded-lg mb-4 text-sm resize-none focus:ring-2 focus:ring-primary-500"
                      />
                      <button
                        onClick={() => generateChapter.mutate()}
                        disabled={generateChapter.isPending}
                        className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 font-medium"
                      >
                        Kapitel generieren
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
