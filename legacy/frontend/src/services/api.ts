import axios from 'axios'
import { QuizState } from '../store/quiz'

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

// Helper to convert quiz state to backend story DNA format
function quizStateToStoryDNA(quiz: QuizState) {
  return {
    spark: {
      spark_type: quiz.spark.sparkType || 'idea',
      description: quiz.spark.description,
      emotional_core: null,
    },
    genre: {
      primary_genre: quiz.genre.primaryGenre,
      subgenres: quiz.genre.subGenres,
      tone_dark_light: quiz.genre.toneDark,
      tone_serious_playful: quiz.genre.toneSerious,
      tone_slow_fast: 50, // Default, not in frontend
    },
    world: {
      time_period: quiz.world.timeframe,
      location: quiz.world.location,
      world_type: 'realistic', // Default
      atmosphere_words: quiz.world.atmosphere,
      special_rules: quiz.world.worldRules.length > 0 ? quiz.world.worldRules.join('; ') : null,
    },
    characters: {
      protagonist: {
        archetype: quiz.characters.protagonist.archetype,
        flaw: quiz.characters.protagonist.flaw,
        want: quiz.characters.protagonist.want,
        need: quiz.characters.protagonist.need,
        name_suggestion: null,
      },
      antagonist: quiz.characters.antagonist.type
        ? {
            type: quiz.characters.antagonist.type,
            description: quiz.characters.antagonist.description,
            motivation: null,
          }
        : null,
      ensemble_size: quiz.characters.ensemble.length > 3 ? 'large' : quiz.characters.ensemble.length > 1 ? 'medium' : 'small',
      ensemble_notes: quiz.characters.ensemble.length > 0 ? quiz.characters.ensemble.join(', ') : null,
    },
    conflict: {
      central_question: quiz.conflict.centralQuestion,
      stakes_personal: quiz.conflict.personalStakes,
      stakes_external: quiz.conflict.externalStakes || null,
      stakes_philosophical: quiz.conflict.internalStakes || null,
    },
    structure: {
      structure_type: quiz.structure.structureType.replace('-', '_'),
      target_words: quiz.structure.targetWords,
      chapter_count: quiz.structure.chapterCount,
      pacing: quiz.structure.pacingStyle.replace('-', '_'),
    },
    voice: {
      emulate_author: quiz.voice.mode === 'emulate' ? quiz.voice.authorId : null,
      custom_style: quiz.voice.mode === 'custom' ? JSON.stringify(quiz.voice.customStyle) : null,
      pov: 'third_limited', // Default
      tense: 'past', // Default
    },
  }
}

// Projects API
export const projectsApi = {
  list: () => api.get('/projects'),

  create: (data: { name: string; author_id: string; target_words?: number; seed?: string }) =>
    api.post('/projects', data),

  createWithDNA: (data: { name: string; author_id: string; quiz: QuizState }) =>
    api.post('/projects', {
      name: data.name,
      author_id: data.author_id,
      target_words: data.quiz.structure.targetWords,
      total_chapters: data.quiz.structure.chapterCount,
      story_dna: quizStateToStoryDNA(data.quiz),
    }),

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
  getPhilosophy: (id: string) => api.get(`/authors/${id}/philosophy`),
  getStyleGuide: (id: string) => api.get(`/authors/${id}/style-guide`),
  getCritiqueRubric: (id: string) => api.get(`/authors/${id}/critique-rubric`),
}

// Pipeline API
export const pipelineApi = {
  // Start pipeline
  start: (projectId: number, authorId: string, autoApprove: boolean = false) =>
    api.post(`/pipeline/projects/${projectId}/start`, {
      author_id: authorId,
      auto_approve: autoApprove,
    }),

  // Pause pipeline
  pause: (projectId: number) =>
    api.post(`/pipeline/projects/${projectId}/pause`),

  // Resume pipeline
  resume: (projectId: number) =>
    api.post(`/pipeline/projects/${projectId}/resume`),

  // Get status
  getStatus: (projectId: number) =>
    api.get(`/pipeline/projects/${projectId}/status`),

  // Get phase preview
  getPhasePreview: (projectId: number, phase: string) =>
    api.get(`/pipeline/projects/${projectId}/phases/${phase}/preview`),

  // Approve phase
  approvePhase: (projectId: number, phase: string) =>
    api.post(`/pipeline/projects/${projectId}/phases/${phase}/approve`, {
      approved: true,
    }),

  // Reject phase
  rejectPhase: (projectId: number, phase: string, reason: string) =>
    api.post(`/pipeline/projects/${projectId}/phases/${phase}/approve`, {
      approved: false,
      rejection_reason: reason,
    }),

  // Get artifact
  getArtifact: (projectId: number, artifactType: string, chapter?: number) =>
    api.get(`/pipeline/projects/${projectId}/artifacts/${artifactType}`, {
      params: chapter ? { chapter } : {},
    }),

  // Get pending approvals
  getPendingApprovals: (projectId: number) =>
    api.get(`/pipeline/projects/${projectId}/pending-approvals`),
}
