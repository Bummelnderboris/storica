/**
 * Quiz progress indicator showing the 8 steps.
 */

interface QuizProgressProps {
  currentStep: number
  onStepClick?: (step: number) => void
}

const steps = [
  { num: 1, name: 'Der Funke', icon: '✨' },
  { num: 2, name: 'Genre & Ton', icon: '🎭' },
  { num: 3, name: 'Welt', icon: '🌍' },
  { num: 4, name: 'Charaktere', icon: '👤' },
  { num: 5, name: 'Konflikt', icon: '⚔️' },
  { num: 6, name: 'Struktur', icon: '📐' },
  { num: 7, name: 'Stimme', icon: '🎤' },
  { num: 8, name: 'Review', icon: '✅' },
]

export default function QuizProgress({ currentStep, onStepClick }: QuizProgressProps) {
  return (
    <div className="w-full py-4">
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={step.num} className="flex items-center">
            {/* Step circle */}
            <button
              onClick={() => onStepClick?.(step.num)}
              disabled={step.num > currentStep}
              className={`
                relative flex items-center justify-center w-10 h-10 rounded-full
                transition-all duration-200 font-medium text-sm
                ${
                  step.num === currentStep
                    ? 'bg-primary-600 text-white ring-4 ring-primary-100'
                    : step.num < currentStep
                    ? 'bg-primary-100 text-primary-700 hover:bg-primary-200 cursor-pointer'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }
              `}
            >
              {step.num < currentStep ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <span className="text-lg">{step.icon}</span>
              )}
            </button>

            {/* Connector line */}
            {index < steps.length - 1 && (
              <div
                className={`
                  w-8 h-0.5 mx-1
                  ${step.num < currentStep ? 'bg-primary-300' : 'bg-gray-200'}
                `}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step name */}
      <div className="mt-3 text-center">
        <span className="text-sm text-gray-500">Schritt {currentStep} von 8</span>
        <h2 className="text-lg font-semibold text-gray-900">
          {steps[currentStep - 1].name}
        </h2>
      </div>
    </div>
  )
}
