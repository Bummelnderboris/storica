/**
 * Step 7: Autorstimme
 */

import { useQuery } from '@tanstack/react-query'
import { authorsApi } from '../../../services/api'
import { useQuizStore } from '../../../store/quiz'

interface Author {
  id: string
  name: string
  lived: string
  nationality: string
}

export default function VoiceStep() {
  const { voice, updateVoice } = useQuizStore()

  const { data: authors, isLoading } = useQuery({
    queryKey: ['authors'],
    queryFn: async () => {
      const response = await authorsApi.list()
      return response.data as Author[]
    },
  })

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          Welche Stimme hat deine Geschichte?
        </h3>
        <p className="text-gray-600">
          Wähle einen Autor zum Emulieren oder definiere deinen eigenen Stil.
        </p>
      </div>

      {/* Mode selection */}
      <div className="flex justify-center gap-4">
        <button
          onClick={() => updateVoice({ mode: 'emulate' })}
          className={`
            px-6 py-3 rounded-xl border-2 transition-all
            ${
              voice.mode === 'emulate'
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-gray-200 hover:border-gray-300'
            }
          `}
        >
          <span className="text-2xl block mb-1">📚</span>
          <span className="font-medium">Autor emulieren</span>
        </button>
        <button
          onClick={() => updateVoice({ mode: 'custom' })}
          className={`
            px-6 py-3 rounded-xl border-2 transition-all
            ${
              voice.mode === 'custom'
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-gray-200 hover:border-gray-300'
            }
          `}
        >
          <span className="text-2xl block mb-1">✨</span>
          <span className="font-medium">Eigenen Stil definieren</span>
        </button>
      </div>

      {/* Emulate mode */}
      {voice.mode === 'emulate' && (
        <div className="animate-fadeIn">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Wähle einen Autor
          </label>
          {isLoading ? (
            <div className="text-center py-8 text-gray-500">
              Lade Autoren...
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {authors?.map((author) => (
                <button
                  key={author.id}
                  onClick={() => updateVoice({ authorId: author.id })}
                  className={`
                    p-4 rounded-xl border-2 text-left transition-all
                    ${
                      voice.authorId === author.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <h4 className="font-semibold text-gray-900">{author.name}</h4>
                  <p className="text-sm text-gray-500">{author.lived}</p>
                  <p className="text-sm text-gray-600 mt-1">{author.nationality}</p>
                </button>
              ))}
            </div>
          )}

          {voice.authorId && (
            <div className="mt-6 p-4 bg-primary-50 rounded-xl">
              <p className="text-sm text-primary-700">
                Die KI wird den Stil von{' '}
                <strong>
                  {authors?.find((a) => a.id === voice.authorId)?.name}
                </strong>{' '}
                analysieren und in deiner Geschichte anwenden.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Custom mode */}
      {voice.mode === 'custom' && (
        <div className="animate-fadeIn space-y-6 max-w-2xl mx-auto">
          {/* Sentence length */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Satzlänge
            </label>
            <div className="flex gap-3">
              {[
                { id: 'short', label: 'Kurz', desc: 'Hemingway-Stil' },
                { id: 'mixed', label: 'Gemischt', desc: 'Abwechslungsreich' },
                { id: 'long', label: 'Lang', desc: 'Literarisch' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() =>
                    updateVoice({
                      customStyle: {
                        ...voice.customStyle,
                        sentenceLength: opt.id as typeof voice.customStyle.sentenceLength,
                      },
                    })
                  }
                  className={`
                    flex-1 p-3 rounded-lg border text-center transition-all
                    ${
                      voice.customStyle.sentenceLength === opt.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <span className="font-medium block">{opt.label}</span>
                  <span className="text-xs text-gray-500">{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Vocabulary */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Wortschatz
            </label>
            <div className="flex gap-3">
              {[
                { id: 'simple', label: 'Einfach', desc: 'Zugänglich' },
                { id: 'moderate', label: 'Moderat', desc: 'Ausgewogen' },
                { id: 'complex', label: 'Komplex', desc: 'Anspruchsvoll' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() =>
                    updateVoice({
                      customStyle: {
                        ...voice.customStyle,
                        vocabulary: opt.id as typeof voice.customStyle.vocabulary,
                      },
                    })
                  }
                  className={`
                    flex-1 p-3 rounded-lg border text-center transition-all
                    ${
                      voice.customStyle.vocabulary === opt.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <span className="font-medium block">{opt.label}</span>
                  <span className="text-xs text-gray-500">{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Tone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tonalität (freitext)
            </label>
            <input
              type="text"
              value={voice.customStyle.tone}
              onChange={(e) =>
                updateVoice({
                  customStyle: { ...voice.customStyle, tone: e.target.value },
                })
              }
              placeholder="Z.B. melancholisch, ironisch, warm, distanziert..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* Influences */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Einflüsse (optional)
            </label>
            <p className="text-sm text-gray-500 mb-2">
              Welche Autoren inspirieren dich?
            </p>
            <input
              type="text"
              value={voice.customStyle.influences.join(', ')}
              onChange={(e) =>
                updateVoice({
                  customStyle: {
                    ...voice.customStyle,
                    influences: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  },
                })
              }
              placeholder="Z.B. Virginia Woolf, Kafka, Murakami..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
      )}
    </div>
  )
}
