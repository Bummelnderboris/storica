/**
 * Step 6: Struktur & Pacing
 */

import { useQuizStore } from '../../../store/quiz'

const structures = [
  {
    id: '3-act',
    name: '3-Akt-Struktur',
    icon: '📐',
    description: 'Klassisch: Setup, Konfrontation, Resolution',
    acts: ['Setup (25%)', 'Konfrontation (50%)', 'Auflösung (25%)'],
  },
  {
    id: '5-act',
    name: '5-Akt-Struktur',
    icon: '🎭',
    description: 'Shakespeare-Stil: Exposition bis Katharsis',
    acts: ['Exposition', 'Rising Action', 'Climax', 'Falling Action', 'Denouement'],
  },
  {
    id: 'hero-journey',
    name: 'Heldenreise',
    icon: '🗺️',
    description: "Campbell's Monomythos: 12 Stationen",
    acts: ['Ordinary World', 'Call to Adventure', '...', 'Return with Elixir'],
  },
  {
    id: 'custom',
    name: 'Frei/Experimentell',
    icon: '✨',
    description: 'Keine feste Struktur - lass dich treiben',
    acts: ['Deine eigene Struktur'],
  },
]

const pacingStyles = [
  {
    id: 'slow-burn',
    name: 'Slow Burn',
    icon: '🔥',
    description: 'Langsamer Aufbau, atmosphärisch, literarisch',
  },
  {
    id: 'balanced',
    name: 'Ausgewogen',
    icon: '⚖️',
    description: 'Mix aus ruhigen und actionreichen Momenten',
  },
  {
    id: 'fast-paced',
    name: 'Rasant',
    icon: '⚡',
    description: 'Schnelle Szenen, Cliffhanger, Page-Turner',
  },
]

const wordCountPresets = [
  { words: 30000, label: 'Novella', chapters: '10-12' },
  { words: 45000, label: 'Kurzer Roman', chapters: '15-18' },
  { words: 60000, label: 'Standard Roman', chapters: '20-24' },
  { words: 80000, label: 'Langer Roman', chapters: '28-32' },
  { words: 100000, label: 'Epos', chapters: '35-40' },
  { words: 120000, label: 'Mammutwerk', chapters: '45-50' },
]

export default function StructureStep() {
  const { structure, updateStructure } = useQuizStore()

  const handleWordCountChange = (words: number) => {
    const chaptersPerThousand = 0.4 // Roughly 2500 words per chapter
    const chapters = Math.round(words * chaptersPerThousand / 1000)
    updateStructure({
      targetWords: words,
      chapterCount: Math.max(10, Math.min(chapters, 50)),
    })
  }

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          Wie ist deine Geschichte strukturiert?
        </h3>
        <p className="text-gray-600">
          Wähle eine Erzählstruktur und definiere Umfang und Tempo.
        </p>
      </div>

      {/* Structure Type */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Erzählstruktur
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {structures.map((s) => (
            <button
              key={s.id}
              onClick={() => updateStructure({ structureType: s.id as typeof structure.structureType })}
              className={`
                p-4 rounded-xl border-2 text-left transition-all
                ${
                  structure.structureType === s.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">{s.icon}</span>
                <span className="font-semibold text-gray-900">{s.name}</span>
              </div>
              <p className="text-sm text-gray-600 mb-2">{s.description}</p>
              <div className="flex flex-wrap gap-1">
                {s.acts.map((act, i) => (
                  <span
                    key={i}
                    className="text-xs px-2 py-1 bg-gray-100 rounded text-gray-600"
                  >
                    {act}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Word Count */}
      <div className="max-w-2xl mx-auto">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Ziel-Wortanzahl
        </label>
        <div className="space-y-4">
          <input
            type="range"
            min="30000"
            max="120000"
            step="5000"
            value={structure.targetWords}
            onChange={(e) => handleWordCountChange(parseInt(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-sm text-gray-500">
            <span>30k</span>
            <span className="font-semibold text-primary-600 text-lg">
              {structure.targetWords.toLocaleString()} Wörter
            </span>
            <span>120k</span>
          </div>
          <div className="flex flex-wrap gap-2 justify-center">
            {wordCountPresets.map((preset) => (
              <button
                key={preset.words}
                onClick={() => handleWordCountChange(preset.words)}
                className={`
                  px-3 py-2 rounded-lg text-sm transition-all
                  ${
                    structure.targetWords === preset.words
                      ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-200'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }
                `}
              >
                <span className="font-medium block">{preset.label}</span>
                <span className="text-xs text-gray-500">{preset.chapters} Kapitel</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Estimated chapters */}
      <div className="max-w-md mx-auto bg-gray-50 rounded-xl p-4 text-center">
        <p className="text-sm text-gray-600">
          Geschätzte Kapitelanzahl:{' '}
          <strong className="text-primary-600 text-lg">{structure.chapterCount}</strong>
        </p>
        <p className="text-xs text-gray-500 mt-1">
          (~{Math.round(structure.targetWords / structure.chapterCount).toLocaleString()} Wörter pro Kapitel)
        </p>
      </div>

      {/* Pacing */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Erzähltempo
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {pacingStyles.map((p) => (
            <button
              key={p.id}
              onClick={() => updateStructure({ pacingStyle: p.id as typeof structure.pacingStyle })}
              className={`
                p-4 rounded-xl border-2 text-center transition-all
                ${
                  structure.pacingStyle === p.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <span className="text-3xl block mb-2">{p.icon}</span>
              <span className="font-semibold text-gray-900 block">{p.name}</span>
              <span className="text-sm text-gray-600">{p.description}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
