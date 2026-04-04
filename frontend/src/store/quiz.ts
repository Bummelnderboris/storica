/**
 * Zustand store for Story DNA Quiz state management.
 */

import { create } from 'zustand'

// Step 1: Der Funke (The Spark)
export interface SparkData {
  sparkType: 'image' | 'character' | 'what-if' | 'feeling' | ''
  description: string
}

// Step 2: Genre & Ton
export interface GenreData {
  primaryGenre: string
  subGenres: string[]
  toneDark: number // 0-100 (Dark to Light)
  toneSerious: number // 0-100 (Serious to Playful)
}

// Step 3: Welt & Setting
export interface WorldData {
  timeframe: string
  location: string
  worldRules: string[]
  atmosphere: string[] // 3 words
}

// Step 4: Charaktere
export interface CharacterData {
  protagonist: {
    archetype: string
    flaw: string
    want: string
    need: string
  }
  antagonist: {
    type: string
    description: string
  }
  ensemble: string[]
}

// Step 5: Konflikt & Stakes
export interface ConflictData {
  centralQuestion: string
  personalStakes: string
  externalStakes: string
  internalStakes: string
}

// Step 6: Struktur & Pacing
export interface StructureData {
  structureType: '3-act' | '5-act' | 'hero-journey' | 'custom'
  targetWords: number
  chapterCount: number
  pacingStyle: 'slow-burn' | 'balanced' | 'fast-paced'
}

// Step 7: Autorstimme
export interface VoiceData {
  mode: 'emulate' | 'custom'
  authorId: string // Selected author for emulation
  customStyle: {
    sentenceLength: 'short' | 'mixed' | 'long'
    vocabulary: 'simple' | 'moderate' | 'complex'
    tone: string
    influences: string[]
  }
}

// Step 8: Review (computed from all data)
export interface ReviewData {
  projectName: string
  summary: string
  confirmed: boolean
}

export interface QuizState {
  // Current step (1-8)
  currentStep: number

  // Step data
  spark: SparkData
  genre: GenreData
  world: WorldData
  characters: CharacterData
  conflict: ConflictData
  structure: StructureData
  voice: VoiceData
  review: ReviewData

  // Actions
  setStep: (step: number) => void
  nextStep: () => void
  prevStep: () => void
  updateSpark: (data: Partial<SparkData>) => void
  updateGenre: (data: Partial<GenreData>) => void
  updateWorld: (data: Partial<WorldData>) => void
  updateCharacters: (data: Partial<CharacterData>) => void
  updateConflict: (data: Partial<ConflictData>) => void
  updateStructure: (data: Partial<StructureData>) => void
  updateVoice: (data: Partial<VoiceData>) => void
  updateReview: (data: Partial<ReviewData>) => void
  resetQuiz: () => void
  getStoryDNA: () => StoryDNA
}

export interface StoryDNA {
  spark: SparkData
  genre: GenreData
  world: WorldData
  characters: CharacterData
  conflict: ConflictData
  structure: StructureData
  voice: VoiceData
  projectName: string
}

const initialSparkData: SparkData = {
  sparkType: '',
  description: '',
}

const initialGenreData: GenreData = {
  primaryGenre: '',
  subGenres: [],
  toneDark: 50,
  toneSerious: 50,
}

const initialWorldData: WorldData = {
  timeframe: '',
  location: '',
  worldRules: [],
  atmosphere: [],
}

const initialCharacterData: CharacterData = {
  protagonist: {
    archetype: '',
    flaw: '',
    want: '',
    need: '',
  },
  antagonist: {
    type: '',
    description: '',
  },
  ensemble: [],
}

const initialConflictData: ConflictData = {
  centralQuestion: '',
  personalStakes: '',
  externalStakes: '',
  internalStakes: '',
}

const initialStructureData: StructureData = {
  structureType: '3-act',
  targetWords: 45000,
  chapterCount: 18,
  pacingStyle: 'balanced',
}

const initialVoiceData: VoiceData = {
  mode: 'emulate',
  authorId: '',
  customStyle: {
    sentenceLength: 'mixed',
    vocabulary: 'moderate',
    tone: '',
    influences: [],
  },
}

const initialReviewData: ReviewData = {
  projectName: '',
  summary: '',
  confirmed: false,
}

export const useQuizStore = create<QuizState>((set, get) => ({
  currentStep: 1,
  spark: initialSparkData,
  genre: initialGenreData,
  world: initialWorldData,
  characters: initialCharacterData,
  conflict: initialConflictData,
  structure: initialStructureData,
  voice: initialVoiceData,
  review: initialReviewData,

  setStep: (step) => set({ currentStep: Math.min(Math.max(step, 1), 8) }),

  nextStep: () =>
    set((state) => ({
      currentStep: Math.min(state.currentStep + 1, 8),
    })),

  prevStep: () =>
    set((state) => ({
      currentStep: Math.max(state.currentStep - 1, 1),
    })),

  updateSpark: (data) =>
    set((state) => ({
      spark: { ...state.spark, ...data },
    })),

  updateGenre: (data) =>
    set((state) => ({
      genre: { ...state.genre, ...data },
    })),

  updateWorld: (data) =>
    set((state) => ({
      world: { ...state.world, ...data },
    })),

  updateCharacters: (data) =>
    set((state) => ({
      characters: {
        ...state.characters,
        ...data,
        protagonist: {
          ...state.characters.protagonist,
          ...(data.protagonist || {}),
        },
        antagonist: {
          ...state.characters.antagonist,
          ...(data.antagonist || {}),
        },
      },
    })),

  updateConflict: (data) =>
    set((state) => ({
      conflict: { ...state.conflict, ...data },
    })),

  updateStructure: (data) =>
    set((state) => ({
      structure: { ...state.structure, ...data },
    })),

  updateVoice: (data) =>
    set((state) => ({
      voice: {
        ...state.voice,
        ...data,
        customStyle: {
          ...state.voice.customStyle,
          ...(data.customStyle || {}),
        },
      },
    })),

  updateReview: (data) =>
    set((state) => ({
      review: { ...state.review, ...data },
    })),

  resetQuiz: () =>
    set({
      currentStep: 1,
      spark: initialSparkData,
      genre: initialGenreData,
      world: initialWorldData,
      characters: initialCharacterData,
      conflict: initialConflictData,
      structure: initialStructureData,
      voice: initialVoiceData,
      review: initialReviewData,
    }),

  getStoryDNA: () => {
    const state = get()
    return {
      spark: state.spark,
      genre: state.genre,
      world: state.world,
      characters: state.characters,
      conflict: state.conflict,
      structure: state.structure,
      voice: state.voice,
      projectName: state.review.projectName,
    }
  },
}))
