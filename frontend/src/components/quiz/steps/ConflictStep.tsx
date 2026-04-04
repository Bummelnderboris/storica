/**
 * Step 5: Konflikt & Stakes
 */

import { useQuizStore } from '../../../store/quiz'

const exampleQuestions = [
  'Kann Liebe alte Wunden heilen?',
  'Ist Rache jemals gerechtfertigt?',
  'Was macht uns menschlich?',
  'Können wir unserer Vergangenheit entkommen?',
  'Was sind wir bereit zu opfern?',
  'Lohnt es sich, für das Richtige zu kämpfen?',
  'Kann man einem Monster vergeben?',
  'Was ist der Preis der Wahrheit?',
]

export default function ConflictStep() {
  const { conflict, updateConflict } = useQuizStore()

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          Worum geht es wirklich?
        </h3>
        <p className="text-gray-600">
          Definiere die zentrale Frage und was auf dem Spiel steht.
        </p>
      </div>

      {/* Central Question */}
      <div className="max-w-2xl mx-auto">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Die zentrale Frage deiner Geschichte
        </label>
        <input
          type="text"
          value={conflict.centralQuestion}
          onChange={(e) => updateConflict({ centralQuestion: e.target.value })}
          placeholder="Was ist die eine Frage, die deine Geschichte beantwortet?"
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 text-lg"
        />
        <div className="mt-3">
          <p className="text-sm text-gray-500 mb-2">Beispiele zur Inspiration:</p>
          <div className="flex flex-wrap gap-2">
            {exampleQuestions.map((q) => (
              <button
                key={q}
                onClick={() => updateConflict({ centralQuestion: q })}
                className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stakes */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Personal Stakes */}
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">💔</span>
            <h4 className="font-semibold text-gray-900">Persönliche Stakes</h4>
          </div>
          <p className="text-sm text-gray-500 mb-3">
            Was verliert der Protagonist emotional?
          </p>
          <textarea
            value={conflict.personalStakes}
            onChange={(e) => updateConflict({ personalStakes: e.target.value })}
            rows={4}
            placeholder="Z.B. Verlust der einzigen Person, die ihn noch liebt..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 text-sm resize-none"
          />
        </div>

        {/* External Stakes */}
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🌍</span>
            <h4 className="font-semibold text-gray-900">Externe Stakes</h4>
          </div>
          <p className="text-sm text-gray-500 mb-3">
            Was steht für die Welt auf dem Spiel?
          </p>
          <textarea
            value={conflict.externalStakes}
            onChange={(e) => updateConflict({ externalStakes: e.target.value })}
            rows={4}
            placeholder="Z.B. Das Dorf wird zerstört, wenn der Drache nicht besiegt wird..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 text-sm resize-none"
          />
        </div>

        {/* Internal Stakes */}
        <div className="bg-white rounded-xl border p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">🧠</span>
            <h4 className="font-semibold text-gray-900">Interne Stakes</h4>
          </div>
          <p className="text-sm text-gray-500 mb-3">
            Welche innere Veränderung droht?
          </p>
          <textarea
            value={conflict.internalStakes}
            onChange={(e) => updateConflict({ internalStakes: e.target.value })}
            rows={4}
            placeholder="Z.B. Er wird zu dem Monster, das er bekämpft..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 text-sm resize-none"
          />
        </div>
      </div>

      {/* Visual Summary */}
      {(conflict.personalStakes || conflict.externalStakes || conflict.internalStakes) && (
        <div className="max-w-2xl mx-auto bg-gray-50 rounded-xl p-6">
          <h4 className="font-semibold text-gray-900 mb-3">Dein Konflikt-Profil</h4>
          <div className="space-y-2">
            {conflict.centralQuestion && (
              <p className="text-gray-700">
                <strong>Zentrale Frage:</strong> {conflict.centralQuestion}
              </p>
            )}
            <div className="flex gap-4 text-sm">
              {conflict.personalStakes && (
                <span className="px-2 py-1 bg-pink-100 text-pink-700 rounded">
                  Persönlich: Stark
                </span>
              )}
              {conflict.externalStakes && (
                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                  Extern: Stark
                </span>
              )}
              {conflict.internalStakes && (
                <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
                  Intern: Stark
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
