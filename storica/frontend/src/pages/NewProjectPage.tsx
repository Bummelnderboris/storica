import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { projectsApi, authorsApi } from '../services/api'

interface Author {
  id: string
  name: string
  lived: string
  nationality: string
}

export default function NewProjectPage() {
  const [name, setName] = useState('')
  const [authorId, setAuthorId] = useState('')
  const [targetWords, setTargetWords] = useState(45000)
  const [seed, setSeed] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: authorsData, isLoading: authorsLoading } = useQuery({
    queryKey: ['authors'],
    queryFn: async () => {
      const response = await authorsApi.list()
      return response.data as Author[]
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; author_id: string; target_words: number; seed?: string }) =>
      projectsApi.create(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate(`/projects/${response.data.id}`)
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to create project')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!authorId) {
      setError('Please select an author style')
      return
    }

    createMutation.mutate({
      name,
      author_id: authorId,
      target_words: targetWords,
      seed: seed || undefined,
    })
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Create New Project</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md text-sm">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
            Project Name
          </label>
          <input
            id="name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Novel"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label htmlFor="author" className="block text-sm font-medium text-gray-700 mb-1">
            Author Style
          </label>
          {authorsLoading ? (
            <div className="text-gray-500">Loading authors...</div>
          ) : (
            <select
              id="author"
              value={authorId}
              onChange={(e) => setAuthorId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">Select an author style</option>
              {authorsData?.map((author) => (
                <option key={author.id} value={author.id}>
                  {author.name} ({author.lived}) - {author.nationality}
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label htmlFor="targetWords" className="block text-sm font-medium text-gray-700 mb-1">
            Target Word Count
          </label>
          <input
            id="targetWords"
            type="number"
            min={10000}
            max={200000}
            step={5000}
            value={targetWords}
            onChange={(e) => setTargetWords(parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <p className="text-sm text-gray-500 mt-1">
            Recommended: 40,000-60,000 for a standard novel
          </p>
        </div>

        <div>
          <label htmlFor="seed" className="block text-sm font-medium text-gray-700 mb-1">
            Story Seed (Optional)
          </label>
          <textarea
            id="seed"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            rows={4}
            placeholder="A brief concept or theme for your story. This will guide the initial essence generation."
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="flex justify-end gap-4">
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="px-4 py-2 text-gray-700 hover:text-gray-900"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </form>
    </div>
  )
}
