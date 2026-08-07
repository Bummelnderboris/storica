/**
 * Story Bible Page - Characters, Locations, Timeline, Plot Threads.
 */

import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '../services/api'

interface StoryBible {
  characters?: Record<string, CharacterEntry>
  locations?: Record<string, LocationEntry>
  plot_threads?: Record<string, PlotThread>
  timeline?: TimelineEntry[]
  consistency_notes?: string[]
}

interface CharacterEntry {
  full_name?: string
  role?: string
  current_state?: string
  new_details?: string[]
}

interface LocationEntry {
  description?: string
  details?: string[]
}

interface PlotThread {
  status?: string
  current_state?: string
  details?: string
}

interface TimelineEntry {
  chapter: number
  time?: string
  events?: string[]
}

type BibleTab = 'characters' | 'locations' | 'timeline' | 'threads' | 'notes'

export default function StoryBiblePage() {
  const { id } = useParams<{ id: string }>()
  const projectId = parseInt(id!)
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<BibleTab>('characters')

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: async () => {
      const response = await projectsApi.get(projectId)
      return response.data
    },
  })

  const { data: storyBible, isLoading } = useQuery({
    queryKey: ['project', projectId, 'story-bible'],
    queryFn: async () => {
      const response = await projectsApi.getStoryBible(projectId)
      // Parse YAML content if it's a string
      if (typeof response.data.content === 'string') {
        try {
          // Simple YAML-like parsing for demo (in prod, use proper yaml parser)
          return JSON.parse(response.data.content) as StoryBible
        } catch {
          return {} as StoryBible
        }
      }
      return response.data as StoryBible
    },
    enabled: project?.content_summary?.has_story_bible,
  })

  const tabs: { id: BibleTab; label: string; icon: string }[] = [
    { id: 'characters', label: 'Charaktere', icon: '👤' },
    { id: 'locations', label: 'Orte', icon: '🗺️' },
    { id: 'timeline', label: 'Timeline', icon: '📅' },
    { id: 'threads', label: 'Plot-Threads', icon: '🧵' },
    { id: 'notes', label: 'Notizen', icon: '📝' },
  ]

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const characters = storyBible?.characters || {}
  const locations = storyBible?.locations || {}
  const plotThreads = storyBible?.plot_threads || {}
  const timeline = storyBible?.timeline || []
  const notes = storyBible?.consistency_notes || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            className="text-gray-500 hover:text-gray-700 mb-2 flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Zurück zum Projekt
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Story Bible</h1>
          <p className="text-gray-600">{project?.name}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border">
        <div className="border-b">
          <nav className="flex">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  px-4 py-3 text-sm font-medium border-b-2 flex items-center gap-2
                  ${
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }
                `}
              >
                <span>{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {/* Characters */}
          {activeTab === 'characters' && (
            <div className="space-y-4">
              {Object.keys(characters).length === 0 ? (
                <EmptyState
                  message="Noch keine Charaktere dokumentiert."
                  hint="Charaktere werden automatisch hinzugefügt, wenn Kapitel generiert werden."
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(characters).map(([id, char]) => (
                    <div key={id} className="border rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900">
                        {char.full_name || id}
                      </h3>
                      {char.role && (
                        <span className="text-xs px-2 py-0.5 bg-primary-100 text-primary-700 rounded-full">
                          {char.role}
                        </span>
                      )}
                      {char.current_state && (
                        <p className="text-sm text-gray-600 mt-2">{char.current_state}</p>
                      )}
                      {char.new_details && char.new_details.length > 0 && (
                        <ul className="mt-2 text-sm text-gray-500 list-disc list-inside">
                          {char.new_details.map((detail, i) => (
                            <li key={i}>{detail}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Locations */}
          {activeTab === 'locations' && (
            <div className="space-y-4">
              {Object.keys(locations).length === 0 ? (
                <EmptyState
                  message="Noch keine Orte dokumentiert."
                  hint="Orte werden automatisch hinzugefügt, wenn sie in Kapiteln erscheinen."
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(locations).map(([id, loc]) => (
                    <div key={id} className="border rounded-lg p-4">
                      <h3 className="font-semibold text-gray-900">{id}</h3>
                      {loc.description && (
                        <p className="text-sm text-gray-600 mt-2">{loc.description}</p>
                      )}
                      {loc.details && loc.details.length > 0 && (
                        <ul className="mt-2 text-sm text-gray-500 list-disc list-inside">
                          {loc.details.map((detail, i) => (
                            <li key={i}>{detail}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Timeline */}
          {activeTab === 'timeline' && (
            <div className="space-y-4">
              {timeline.length === 0 ? (
                <EmptyState
                  message="Noch keine Timeline-Einträge."
                  hint="Die Timeline wird während der Kapitel-Generierung aufgebaut."
                />
              ) : (
                <div className="relative">
                  <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />
                  <div className="space-y-6">
                    {timeline.map((entry, i) => (
                      <div key={i} className="relative pl-10">
                        <div className="absolute left-2.5 w-3 h-3 bg-primary-500 rounded-full" />
                        <div className="border rounded-lg p-4">
                          <div className="flex justify-between items-center mb-2">
                            <span className="font-semibold text-gray-900">
                              Kapitel {entry.chapter}
                            </span>
                            {entry.time && (
                              <span className="text-sm text-gray-500">{entry.time}</span>
                            )}
                          </div>
                          {entry.events && (
                            <ul className="text-sm text-gray-600 list-disc list-inside">
                              {entry.events.map((event, j) => (
                                <li key={j}>{event}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Plot Threads */}
          {activeTab === 'threads' && (
            <div className="space-y-4">
              {Object.keys(plotThreads).length === 0 ? (
                <EmptyState
                  message="Noch keine Plot-Threads dokumentiert."
                  hint="Plot-Threads werden automatisch erkannt und verfolgt."
                />
              ) : (
                <div className="space-y-4">
                  {Object.entries(plotThreads).map(([id, thread]) => (
                    <div key={id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-gray-900">{id}</h3>
                        {thread.status && (
                          <span
                            className={`
                              text-xs px-2 py-0.5 rounded-full
                              ${
                                thread.status === 'active'
                                  ? 'bg-green-100 text-green-700'
                                  : thread.status === 'resolved'
                                  ? 'bg-gray-100 text-gray-700'
                                  : 'bg-amber-100 text-amber-700'
                              }
                            `}
                          >
                            {thread.status}
                          </span>
                        )}
                      </div>
                      {(thread.current_state || thread.details) && (
                        <p className="text-sm text-gray-600">
                          {thread.current_state || thread.details}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Notes */}
          {activeTab === 'notes' && (
            <div className="space-y-4">
              {notes.length === 0 ? (
                <EmptyState
                  message="Noch keine Konsistenz-Notizen."
                  hint="Wichtige Details werden hier gesammelt um Konsistenz zu wahren."
                />
              ) : (
                <ul className="space-y-2">
                  {notes.map((note, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-100 rounded-lg"
                    >
                      <span className="text-amber-600">📌</span>
                      <span className="text-sm text-gray-700">{note}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EmptyState({ message, hint }: { message: string; hint: string }) {
  return (
    <div className="text-center py-12">
      <div className="text-4xl mb-3">📖</div>
      <p className="text-gray-600 mb-2">{message}</p>
      <p className="text-sm text-gray-400">{hint}</p>
    </div>
  )
}
