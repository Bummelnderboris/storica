/**
 * Verbosity level selector for activity log.
 */

import { VerbosityLevel } from './types'

interface VerbositySelectorProps {
  value: VerbosityLevel
  onChange: (level: VerbosityLevel) => void
}

const levels: { id: VerbosityLevel; label: string; description: string }[] = [
  {
    id: 'minimal',
    label: 'Minimal',
    description: 'Nur Schritte + Kosten',
  },
  {
    id: 'normal',
    label: 'Normal',
    description: 'Schritte + Artefakte + Entscheidungen',
  },
  {
    id: 'detailed',
    label: 'Detailliert',
    description: 'Alles inkl. Denkprozess',
  },
]

export default function VerbositySelector({
  value,
  onChange,
}: VerbositySelectorProps) {
  return (
    <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
      {levels.map((level) => (
        <button
          key={level.id}
          onClick={() => onChange(level.id)}
          title={level.description}
          className={`
            px-3 py-1 text-xs font-medium rounded-md transition-all
            ${
              value === level.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }
          `}
        >
          {level.label}
        </button>
      ))}
    </div>
  )
}
