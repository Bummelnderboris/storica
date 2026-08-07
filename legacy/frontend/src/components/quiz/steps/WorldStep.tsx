/**
 * Step 3: Welt & Setting
 */

import { useState } from 'react'
import { useQuizStore } from '../../../store/quiz'

const timeframes = [
  { id: 'ancient', name: 'Antike', range: 'vor 500 n.Chr.' },
  { id: 'medieval', name: 'Mittelalter', range: '500-1500' },
  { id: 'early-modern', name: 'Frühe Neuzeit', range: '1500-1800' },
  { id: 'victorian', name: 'Viktorianisch', range: '1800-1900' },
  { id: '20th', name: '20. Jahrhundert', range: '1900-2000' },
  { id: 'contemporary', name: 'Gegenwart', range: '2000+' },
  { id: 'near-future', name: 'Nahe Zukunft', range: '+50 Jahre' },
  { id: 'far-future', name: 'Ferne Zukunft', range: '+500 Jahre' },
  { id: 'timeless', name: 'Zeitlos', range: 'Fantasy/Märchen' },
]

const locationTypes = [
  'Großstadt',
  'Kleinstadt',
  'Dorf',
  'Wildnis',
  'Meer/Schiff',
  'Berge',
  'Wüste',
  'Insel',
  'Raumstation',
  'Fremde Welt',
  'Parallelwelt',
  'Untergrund',
]

const atmosphereWords = [
  'geheimnisvoll',
  'bedrohlich',
  'nostalgisch',
  'hoffnungsvoll',
  'melancholisch',
  'aufregend',
  'friedlich',
  'chaotisch',
  'romantisch',
  'düster',
  'magisch',
  'realistisch',
  'surreal',
  'warm',
  'kalt',
  'lebendig',
]

export default function WorldStep() {
  const { world, updateWorld } = useQuizStore()
  const [customRule, setCustomRule] = useState('')

  const toggleAtmosphere = (word: string) => {
    const newAtmosphere = world.atmosphere.includes(word)
      ? world.atmosphere.filter((w) => w !== word)
      : [...world.atmosphere, word].slice(0, 3)
    updateWorld({ atmosphere: newAtmosphere })
  }

  const addWorldRule = () => {
    if (customRule.trim() && world.worldRules.length < 5) {
      updateWorld({ worldRules: [...world.worldRules, customRule.trim()] })
      setCustomRule('')
    }
  }

  const removeWorldRule = (rule: string) => {
    updateWorld({ worldRules: world.worldRules.filter((r) => r !== rule) })
  }

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          In welcher Welt spielt deine Geschichte?
        </h3>
        <p className="text-gray-600">
          Definiere Zeit, Ort und die Regeln deiner Welt.
        </p>
      </div>

      {/* Timeframe */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Zeitrahmen
        </label>
        <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
          {timeframes.map((tf) => (
            <button
              key={tf.id}
              onClick={() => updateWorld({ timeframe: tf.id })}
              className={`
                p-3 rounded-lg border text-center transition-all
                ${
                  world.timeframe === tf.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <span className="text-sm font-medium block">{tf.name}</span>
              <span className="text-xs text-gray-500">{tf.range}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Location */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Hauptschauplatz
        </label>
        <div className="flex flex-wrap gap-2">
          {locationTypes.map((loc) => (
            <button
              key={loc}
              onClick={() => updateWorld({ location: loc })}
              className={`
                px-4 py-2 rounded-full text-sm font-medium transition-all
                ${
                  world.location === loc
                    ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-200'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              `}
            >
              {loc}
            </button>
          ))}
        </div>
      </div>

      {/* World rules */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Weltregeln (optional, max. 5)
        </label>
        <p className="text-sm text-gray-500 mb-3">
          Was macht deine Welt besonders? Z.B. "Magie existiert, aber kostet Lebenszeit"
        </p>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={customRule}
            onChange={(e) => setCustomRule(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addWorldRule()}
            placeholder="Eine Regel deiner Welt..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={addWorldRule}
            disabled={!customRule.trim() || world.worldRules.length >= 5}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            +
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {world.worldRules.map((rule) => (
            <span
              key={rule}
              className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 rounded-full text-sm"
            >
              {rule}
              <button
                onClick={() => removeWorldRule(rule)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Atmosphere */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Atmosphäre (3 Wörter)
        </label>
        <div className="flex flex-wrap gap-2">
          {atmosphereWords.map((word) => (
            <button
              key={word}
              onClick={() => toggleAtmosphere(word)}
              disabled={world.atmosphere.length >= 3 && !world.atmosphere.includes(word)}
              className={`
                px-4 py-2 rounded-full text-sm font-medium transition-all
                ${
                  world.atmosphere.includes(word)
                    ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-200'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50'
                }
              `}
            >
              {word}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
