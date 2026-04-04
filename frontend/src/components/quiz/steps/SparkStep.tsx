/**
 * Step 1: Der Funke (The Spark)
 * Where does the idea come from?
 */

import { useQuizStore, SparkData } from '../../../store/quiz'

const sparkTypes = [
  {
    id: 'image',
    icon: '🖼️',
    title: 'Ein Bild',
    description: 'Eine Szene, die du vor dir siehst',
  },
  {
    id: 'character',
    icon: '👤',
    title: 'Ein Charakter',
    description: 'Eine Person, die dich fasziniert',
  },
  {
    id: 'what-if',
    icon: '🤔',
    title: 'Was wäre wenn...',
    description: 'Eine Frage, die dich nicht loslässt',
  },
  {
    id: 'feeling',
    icon: '💫',
    title: 'Ein Gefühl',
    description: 'Eine Emotion, die du vermitteln willst',
  },
]

export default function SparkStep() {
  const { spark, updateSpark } = useQuizStore()

  const handleTypeSelect = (type: SparkData['sparkType']) => {
    updateSpark({ sparkType: type })
  }

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateSpark({ description: e.target.value })
  }

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          Woher kommt deine Idee?
        </h3>
        <p className="text-gray-600">
          Jede große Geschichte beginnt mit einem Funken. Was hat dich inspiriert?
        </p>
      </div>

      {/* Spark type selection */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {sparkTypes.map((type) => (
          <button
            key={type.id}
            onClick={() => handleTypeSelect(type.id as SparkData['sparkType'])}
            className={`
              p-4 rounded-xl border-2 text-left transition-all
              ${
                spark.sparkType === type.id
                  ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }
            `}
          >
            <span className="text-3xl block mb-2">{type.icon}</span>
            <h4 className="font-medium text-gray-900">{type.title}</h4>
            <p className="text-sm text-gray-500 mt-1">{type.description}</p>
          </button>
        ))}
      </div>

      {/* Description input */}
      {spark.sparkType && (
        <div className="max-w-2xl mx-auto animate-fadeIn">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Beschreibe deinen Funken
          </label>
          <textarea
            value={spark.description}
            onChange={handleDescriptionChange}
            rows={5}
            placeholder={
              spark.sparkType === 'image'
                ? 'Beschreibe das Bild, das du siehst...'
                : spark.sparkType === 'character'
                ? 'Wer ist diese Person? Was macht sie besonders?'
                : spark.sparkType === 'what-if'
                ? 'Was wäre wenn...?'
                : 'Welches Gefühl willst du beim Leser erzeugen?'
            }
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none"
          />
          <p className="text-sm text-gray-500 mt-2">
            Keine Sorge, das muss nicht perfekt sein. Es ist nur der Ausgangspunkt.
          </p>
        </div>
      )}
    </div>
  )
}
