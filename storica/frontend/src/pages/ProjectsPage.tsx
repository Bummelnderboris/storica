import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { projectsApi } from '../services/api'

interface Project {
  id: number
  name: string
  author_id: string
  target_words: number
  current_stage: string
  current_chapter: number
  total_chapters: number
  created_at: string
  updated_at: string
}

export default function ProjectsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await projectsApi.list()
      return response.data as { projects: Project[]; total: number }
    },
  })

  const getStageLabel = (stage: string) => {
    const labels: Record<string, string> = {
      essence: 'Essence',
      architecture: 'Architecture',
      blueprint: 'Blueprints',
      prose: 'Writing',
      polish: 'Polishing',
      complete: 'Complete',
    }
    return labels[stage] || stage
  }

  const getStageColor = (stage: string) => {
    const colors: Record<string, string> = {
      essence: 'bg-purple-100 text-purple-800',
      architecture: 'bg-blue-100 text-blue-800',
      blueprint: 'bg-yellow-100 text-yellow-800',
      prose: 'bg-green-100 text-green-800',
      polish: 'bg-orange-100 text-orange-800',
      complete: 'bg-gray-100 text-gray-800',
    }
    return colors[stage] || 'bg-gray-100 text-gray-800'
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-red-600">
        Failed to load projects
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <Link
          to="/projects/new"
          className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
        >
          New Project
        </Link>
      </div>

      {data?.projects.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow-sm">
          <h3 className="text-lg font-medium text-gray-900 mb-2">No projects yet</h3>
          <p className="text-gray-600 mb-4">Create your first novel project to get started.</p>
          <Link
            to="/projects/new"
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
          >
            Create Project
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {data?.projects.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="bg-white rounded-lg shadow-sm border p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{project.name}</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Author style: {project.author_id} | Target: {project.target_words.toLocaleString()} words
                  </p>
                </div>
                <span
                  className={`px-2 py-1 text-xs font-medium rounded-full ${getStageColor(project.current_stage)}`}
                >
                  {getStageLabel(project.current_stage)}
                </span>
              </div>

              {project.total_chapters > 0 && (
                <div className="mt-4">
                  <div className="flex justify-between text-sm text-gray-600 mb-1">
                    <span>Progress</span>
                    <span>
                      {project.current_chapter} / {project.total_chapters} chapters
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-primary-500 h-2 rounded-full"
                      style={{
                        width: `${(project.current_chapter / project.total_chapters) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              <div className="mt-4 text-xs text-gray-500">
                Last updated: {new Date(project.updated_at).toLocaleDateString()}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
