import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const response = await axios.post('/api/auth/refresh', null, {
            headers: { Authorization: `Bearer ${refreshToken}` },
          })

          const { access_token, refresh_token } = response.data
          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', refresh_token)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        }
      } catch {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post('/auth/register', data),

  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),

  refresh: () => api.post('/auth/refresh'),

  me: () => api.get('/auth/me'),
}

// Projects API
export const projectsApi = {
  list: () => api.get('/projects'),

  create: (data: { name: string; author_id: string; target_words?: number; seed?: string }) =>
    api.post('/projects', data),

  get: (id: number) => api.get(`/projects/${id}`),

  update: (id: number, data: { name?: string; seed?: string; target_words?: number }) =>
    api.patch(`/projects/${id}`, data),

  delete: (id: number) => api.delete(`/projects/${id}`),

  getEssence: (id: number) => api.get(`/projects/${id}/essence`),
  getArchitecture: (id: number) => api.get(`/projects/${id}/architecture`),
  getStoryBible: (id: number) => api.get(`/projects/${id}/story-bible`),
  getBlueprints: (id: number) => api.get(`/projects/${id}/blueprints`),
  getBlueprint: (id: number, chapterNum: number) =>
    api.get(`/projects/${id}/blueprints/${chapterNum}`),
  getChapters: (id: number) => api.get(`/projects/${id}/chapters`),
  getChapter: (id: number, chapterNum: number) =>
    api.get(`/projects/${id}/chapters/${chapterNum}`),
}

// Generation API
export const generationApi = {
  generateEssence: (projectId: number, guidance?: string) =>
    api.post(`/generation/projects/${projectId}/generate/essence`, { guidance }),

  generateArchitecture: (projectId: number, guidance?: string) =>
    api.post(`/generation/projects/${projectId}/generate/architecture`, { guidance }),

  generateBlueprint: (projectId: number, chapterNum: number, guidance?: string) =>
    api.post(`/generation/projects/${projectId}/generate/blueprint/${chapterNum}`, { guidance }),

  generateChapter: (projectId: number, chapterNum: number, guidance?: string) =>
    api.post(`/generation/projects/${projectId}/generate/chapter/${chapterNum}`, { guidance }),

  getTask: (taskId: number) => api.get(`/generation/tasks/${taskId}`),

  approveTask: (taskId: number, approved: boolean = true) =>
    api.post(`/generation/tasks/${taskId}/approve`, { approved }),

  regenerateTask: (taskId: number, guidance: string) =>
    api.post(`/generation/tasks/${taskId}/regenerate`, { guidance }),

  listTasks: (projectId: number) => api.get(`/generation/projects/${projectId}/tasks`),
}

// Authors API
export const authorsApi = {
  list: () => api.get('/authors'),
  get: (id: string) => api.get(`/authors/${id}`),
}
