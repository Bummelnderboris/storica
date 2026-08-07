/**
 * Main Quiz Container - orchestrates the 8-step Story DNA Quiz.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useQuizStore } from '../../store/quiz'
import { projectsApi } from '../../services/api'
import QuizProgress from './QuizProgress'

// Step components
import SparkStep from './steps/SparkStep'
import GenreStep from './steps/GenreStep'
import WorldStep from './steps/WorldStep'
import CharactersStep from './steps/CharactersStep'
import ConflictStep from './steps/ConflictStep'
import StructureStep from './steps/StructureStep'
import VoiceStep from './steps/VoiceStep'
import ReviewStep from './steps/ReviewStep'

const steps = [
  { component: SparkStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => !!s.spark.sparkType },
  { component: GenreStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => !!s.genre.primaryGenre },
  { component: WorldStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => !!s.world.timeframe },
  { component: CharactersStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => !!s.characters.protagonist.archetype },
  { component: ConflictStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => !!s.conflict.centralQuestion },
  { component: StructureStep, validate: () => true }, // Has defaults
  { component: VoiceStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => s.voice.mode === 'custom' || !!s.voice.authorId },
  { component: ReviewStep, validate: (s: ReturnType<typeof useQuizStore.getState>) => !!s.review.projectName },
]

export default function QuizContainer() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const store = useQuizStore()
  const { currentStep, nextStep, prevStep, setStep, resetQuiz, getStoryDNA } = store

  const currentStepIndex = currentStep - 1
  const StepComponent = steps[currentStepIndex]?.component
  const canProceed = steps[currentStepIndex]?.validate(store)

  // Create project mutation - sends full Story DNA to backend
  const createProjectMutation = useMutation({
    mutationFn: async () => {
      const dna = getStoryDNA()

      // Determine author_id
      const authorId = dna.voice.mode === 'emulate' ? dna.voice.authorId : 'custom'

      return projectsApi.createWithDNA({
        name: dna.projectName,
        author_id: authorId,
        quiz: store,
      })
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      resetQuiz()
      navigate(`/projects/${response.data.id}`)
    },
  })

  const handleNext = () => {
    if (currentStep === 8) {
      // Final step - create project
      createProjectMutation.mutate()
    } else {
      nextStep()
    }
  }

  const handleCancel = () => {
    resetQuiz()
    navigate('/projects')
  }

  const handleStepClick = (step: number) => {
    // Only allow going back, not forward (unless validated)
    if (step < currentStep) {
      setStep(step)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Story DNA Quiz</h1>
        <p className="text-gray-600">
          Entdecke die DNA deiner Geschichte in 8 Schritten.
        </p>
      </div>

      {/* Progress */}
      <QuizProgress currentStep={currentStep} onStepClick={handleStepClick} />

      {/* Step Content */}
      <div className="bg-white rounded-2xl shadow-sm border p-6 md:p-8 my-6 min-h-[400px]">
        {StepComponent && <StepComponent />}
      </div>

      {/* Error message */}
      {createProjectMutation.isError && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          Fehler beim Erstellen des Projekts. Bitte versuche es erneut.
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button
          onClick={currentStep === 1 ? handleCancel : prevStep}
          className="px-6 py-2 text-gray-600 hover:text-gray-900"
        >
          {currentStep === 1 ? 'Abbrechen' : 'Zurück'}
        </button>

        <div className="flex items-center gap-2">
          {!canProceed && currentStep < 8 && (
            <span className="text-sm text-amber-600">
              Bitte fülle die erforderlichen Felder aus
            </span>
          )}
          <button
            onClick={handleNext}
            disabled={!canProceed || createProjectMutation.isPending}
            className={`
              px-6 py-2 rounded-lg font-medium transition-all
              ${
                canProceed
                  ? 'bg-primary-600 text-white hover:bg-primary-700'
                  : 'bg-gray-200 text-gray-500 cursor-not-allowed'
              }
              disabled:opacity-50
            `}
          >
            {createProjectMutation.isPending
              ? 'Erstelle...'
              : currentStep === 8
              ? 'Projekt erstellen'
              : 'Weiter'}
          </button>
        </div>
      </div>
    </div>
  )
}
