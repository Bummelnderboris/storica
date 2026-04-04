/**
 * Step 4: Charaktere
 */

import { useState } from 'react'
import { useQuizStore } from '../../../store/quiz'

const archetypes = [
  { id: 'hero', name: 'Held/in', desc: 'Auf der Reise zur Selbstverwirklichung' },
  { id: 'orphan', name: 'Waise', desc: 'Sucht Zugehörigkeit und Sicherheit' },
  { id: 'rebel', name: 'Rebell/in', desc: 'Kämpft gegen das System' },
  { id: 'lover', name: 'Liebende/r', desc: 'Sucht Verbindung und Intimität' },
  { id: 'sage', name: 'Weise/r', desc: 'Sucht Wahrheit und Erkenntnis' },
  { id: 'jester', name: 'Narr/Närrin', desc: 'Bringt Freude und Perspektive' },
  { id: 'caregiver', name: 'Beschützer/in', desc: 'Kümmert sich um andere' },
  { id: 'explorer', name: 'Entdecker/in', desc: 'Sucht Freiheit und Abenteuer' },
]

const flaws = [
  'Stolz',
  'Angst',
  'Gier',
  'Naivität',
  'Wut',
  'Misstrauen',
  'Perfektionismus',
  'Selbstzweifel',
  'Kontrollzwang',
  'Flucht',
  'Eifersucht',
  'Sturheit',
]

const antagonistTypes = [
  { id: 'villain', name: 'Klassischer Bösewicht', icon: '😈' },
  { id: 'rival', name: 'Rivale/Konkurrent', icon: '⚔️' },
  { id: 'system', name: 'System/Institution', icon: '🏛️' },
  { id: 'nature', name: 'Natur/Umwelt', icon: '🌪️' },
  { id: 'self', name: 'Innerer Dämon', icon: '🪞' },
  { id: 'society', name: 'Gesellschaft', icon: '👥' },
]

export default function CharactersStep() {
  const { characters, updateCharacters } = useQuizStore()
  const [ensembleInput, setEnsembleInput] = useState('')

  const handleProtagonistChange = (field: string, value: string) => {
    updateCharacters({
      protagonist: { ...characters.protagonist, [field]: value },
    })
  }

  const handleAntagonistChange = (field: string, value: string) => {
    updateCharacters({
      antagonist: { ...characters.antagonist, [field]: value },
    })
  }

  const addEnsembleMember = () => {
    if (ensembleInput.trim() && characters.ensemble.length < 6) {
      updateCharacters({
        ensemble: [...characters.ensemble, ensembleInput.trim()],
      })
      setEnsembleInput('')
    }
  }

  const removeEnsembleMember = (member: string) => {
    updateCharacters({
      ensemble: characters.ensemble.filter((m) => m !== member),
    })
  }

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          Wer sind deine Charaktere?
        </h3>
        <p className="text-gray-600">
          Definiere deinen Protagonisten, Antagonisten und das Ensemble.
        </p>
      </div>

      {/* Protagonist */}
      <div className="bg-white rounded-xl border p-6">
        <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span className="text-2xl">🦸</span> Protagonist/in
        </h4>

        <div className="space-y-4">
          {/* Archetype */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Archetyp
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {archetypes.map((arch) => (
                <button
                  key={arch.id}
                  onClick={() => handleProtagonistChange('archetype', arch.id)}
                  className={`
                    p-2 rounded-lg border text-left transition-all text-sm
                    ${
                      characters.protagonist.archetype === arch.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <span className="font-medium block">{arch.name}</span>
                  <span className="text-xs text-gray-500">{arch.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Flaw */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Charakterschwäche (Flaw)
            </label>
            <div className="flex flex-wrap gap-2">
              {flaws.map((flaw) => (
                <button
                  key={flaw}
                  onClick={() => handleProtagonistChange('flaw', flaw)}
                  className={`
                    px-3 py-1 rounded-full text-sm transition-all
                    ${
                      characters.protagonist.flaw === flaw
                        ? 'bg-red-100 text-red-700 ring-2 ring-red-200'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }
                  `}
                >
                  {flaw}
                </button>
              ))}
            </div>
          </div>

          {/* Want vs Need */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Was will er/sie? (Want)
              </label>
              <input
                type="text"
                value={characters.protagonist.want}
                onChange={(e) => handleProtagonistChange('want', e.target.value)}
                placeholder="Das bewusste Ziel..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Was braucht er/sie? (Need)
              </label>
              <input
                type="text"
                value={characters.protagonist.need}
                onChange={(e) => handleProtagonistChange('need', e.target.value)}
                placeholder="Das unbewusste Bedürfnis..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Antagonist */}
      <div className="bg-white rounded-xl border p-6">
        <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span className="text-2xl">👹</span> Antagonist
        </h4>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Art des Gegenspielers
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {antagonistTypes.map((type) => (
                <button
                  key={type.id}
                  onClick={() => handleAntagonistChange('type', type.id)}
                  className={`
                    p-3 rounded-lg border text-center transition-all
                    ${
                      characters.antagonist.type === type.id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }
                  `}
                >
                  <span className="text-2xl block mb-1">{type.icon}</span>
                  <span className="text-sm font-medium">{type.name}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kurzbeschreibung
            </label>
            <input
              type="text"
              value={characters.antagonist.description}
              onChange={(e) => handleAntagonistChange('description', e.target.value)}
              placeholder="Was treibt den Antagonisten an?"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
      </div>

      {/* Ensemble */}
      <div className="bg-white rounded-xl border p-6">
        <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span className="text-2xl">👥</span> Ensemble (optional)
        </h4>
        <p className="text-sm text-gray-500 mb-4">
          Wichtige Nebencharaktere (max. 6)
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={ensembleInput}
            onChange={(e) => setEnsembleInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addEnsembleMember()}
            placeholder="Name oder Rolle..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={addEnsembleMember}
            disabled={!ensembleInput.trim() || characters.ensemble.length >= 6}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            +
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {characters.ensemble.map((member) => (
            <span
              key={member}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-full"
            >
              {member}
              <button
                onClick={() => removeEnsembleMember(member)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
