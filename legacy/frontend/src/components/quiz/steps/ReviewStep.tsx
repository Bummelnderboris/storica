/**
 * Step 8: Review
 * Summary of all quiz data with option to edit project name.
 */

import { useQuery } from '@tanstack/react-query'
import { authorsApi } from '../../../services/api'
import { useQuizStore } from '../../../store/quiz'

interface Author {
  id: string
  name: string
}

const genreNames: Record<string, string> = {
  literary: 'Literarisch',
  thriller: 'Thriller',
  romance: 'Romantik',
  fantasy: 'Fantasy',
  scifi: 'Science Fiction',
  mystery: 'Krimi',
  horror: 'Horror',
  historical: 'Historisch',
}

const archetypeNames: Record<string, string> = {
  hero: 'Held/in',
  orphan: 'Waise',
  rebel: 'Rebell/in',
  lover: 'Liebende/r',
  sage: 'Weise/r',
  jester: 'Narr/Närrin',
  caregiver: 'Beschützer/in',
  explorer: 'Entdecker/in',
}

const structureNames: Record<string, string> = {
  '3-act': '3-Akt-Struktur',
  '5-act': '5-Akt-Struktur',
  'hero-journey': 'Heldenreise',
  custom: 'Frei/Experimentell',
}

export default function ReviewStep() {
  const { spark, genre, world, characters, conflict, structure, voice, review, updateReview, setStep } =
    useQuizStore()

  const { data: authors } = useQuery({
    queryKey: ['authors'],
    queryFn: async () => {
      const response = await authorsApi.list()
      return response.data as Author[]
    },
  })

  const selectedAuthor = authors?.find((a) => a.id === voice.authorId)

  return (
    <div className="space-y-6">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          Deine Story DNA
        </h3>
        <p className="text-gray-600">
          Überprüfe deine Eingaben und gib deinem Projekt einen Namen.
        </p>
      </div>

      {/* Project Name */}
      <div className="max-w-md mx-auto">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Projektname
        </label>
        <input
          type="text"
          value={review.projectName}
          onChange={(e) => updateReview({ projectName: e.target.value })}
          placeholder="Mein neuer Roman..."
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 text-lg font-medium text-center"
        />
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl mx-auto">
        {/* Spark */}
        <SummaryCard
          title="Der Funke"
          emoji="✨"
          onEdit={() => setStep(1)}
        >
          <p className="text-sm text-gray-600">
            {spark.sparkType === 'image' && 'Ein Bild: '}
            {spark.sparkType === 'character' && 'Ein Charakter: '}
            {spark.sparkType === 'what-if' && 'Was wäre wenn: '}
            {spark.sparkType === 'feeling' && 'Ein Gefühl: '}
            <span className="text-gray-900">{spark.description || '(nicht ausgefüllt)'}</span>
          </p>
        </SummaryCard>

        {/* Genre */}
        <SummaryCard
          title="Genre & Ton"
          emoji="🎭"
          onEdit={() => setStep(2)}
        >
          <p className="text-sm text-gray-900 font-medium">
            {genreNames[genre.primaryGenre] || genre.primaryGenre || '(nicht gewählt)'}
          </p>
          {genre.subGenres.length > 0 && (
            <p className="text-sm text-gray-600">
              + {genre.subGenres.join(', ')}
            </p>
          )}
          <div className="flex gap-2 mt-2 text-xs">
            <span className="px-2 py-1 bg-gray-100 rounded">
              {genre.toneDark < 50 ? 'Dunkel' : 'Hell'}
            </span>
            <span className="px-2 py-1 bg-gray-100 rounded">
              {genre.toneSerious < 50 ? 'Ernst' : 'Spielerisch'}
            </span>
          </div>
        </SummaryCard>

        {/* World */}
        <SummaryCard
          title="Welt & Setting"
          emoji="🌍"
          onEdit={() => setStep(3)}
        >
          <p className="text-sm text-gray-900">
            {world.location || '(kein Ort)'} • {world.timeframe || '(keine Zeit)'}
          </p>
          {world.atmosphere.length > 0 && (
            <p className="text-sm text-gray-600 mt-1">
              Atmosphäre: {world.atmosphere.join(', ')}
            </p>
          )}
        </SummaryCard>

        {/* Characters */}
        <SummaryCard
          title="Charaktere"
          emoji="👤"
          onEdit={() => setStep(4)}
        >
          <p className="text-sm text-gray-900">
            Protagonist: {archetypeNames[characters.protagonist.archetype] || '(nicht gewählt)'}
          </p>
          {characters.protagonist.flaw && (
            <p className="text-sm text-gray-600">
              Flaw: {characters.protagonist.flaw}
            </p>
          )}
          {characters.antagonist.type && (
            <p className="text-sm text-gray-600">
              Antagonist: {characters.antagonist.type}
            </p>
          )}
        </SummaryCard>

        {/* Conflict */}
        <SummaryCard
          title="Konflikt"
          emoji="⚔️"
          onEdit={() => setStep(5)}
        >
          {conflict.centralQuestion ? (
            <p className="text-sm text-gray-900 italic">"{conflict.centralQuestion}"</p>
          ) : (
            <p className="text-sm text-gray-500">(keine zentrale Frage)</p>
          )}
          <div className="flex gap-2 mt-2 text-xs">
            {conflict.personalStakes && (
              <span className="px-2 py-1 bg-pink-100 text-pink-700 rounded">Persönlich</span>
            )}
            {conflict.externalStakes && (
              <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">Extern</span>
            )}
            {conflict.internalStakes && (
              <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">Intern</span>
            )}
          </div>
        </SummaryCard>

        {/* Structure */}
        <SummaryCard
          title="Struktur"
          emoji="📐"
          onEdit={() => setStep(6)}
        >
          <p className="text-sm text-gray-900">
            {structureNames[structure.structureType] || structure.structureType}
          </p>
          <p className="text-sm text-gray-600">
            {structure.targetWords.toLocaleString()} Wörter • {structure.chapterCount} Kapitel
          </p>
          <span className="inline-block mt-1 text-xs px-2 py-1 bg-gray-100 rounded">
            {structure.pacingStyle === 'slow-burn'
              ? 'Slow Burn'
              : structure.pacingStyle === 'fast-paced'
              ? 'Rasant'
              : 'Ausgewogen'}
          </span>
        </SummaryCard>

        {/* Voice */}
        <SummaryCard
          title="Stimme"
          emoji="🎤"
          onEdit={() => setStep(7)}
          className="md:col-span-2"
        >
          {voice.mode === 'emulate' ? (
            <p className="text-sm text-gray-900">
              Emuliere: <strong>{selectedAuthor?.name || voice.authorId || '(nicht gewählt)'}</strong>
            </p>
          ) : (
            <div className="text-sm text-gray-600 space-y-1">
              <p>
                Sätze: {voice.customStyle.sentenceLength} • Wortschatz: {voice.customStyle.vocabulary}
              </p>
              {voice.customStyle.tone && <p>Ton: {voice.customStyle.tone}</p>}
              {voice.customStyle.influences.length > 0 && (
                <p>Einflüsse: {voice.customStyle.influences.join(', ')}</p>
              )}
            </div>
          )}
        </SummaryCard>
      </div>

      {/* Ready message */}
      <div className="text-center max-w-md mx-auto mt-8 p-4 bg-primary-50 rounded-xl">
        <p className="text-primary-700">
          Wenn du zufrieden bist, klicke auf <strong>"Projekt erstellen"</strong>, um die Story DNA
          zu speichern und mit der Essence-Generierung zu beginnen.
        </p>
      </div>
    </div>
  )
}

interface SummaryCardProps {
  title: string
  emoji: string
  children: React.ReactNode
  onEdit: () => void
  className?: string
}

function SummaryCard({ title, emoji, children, onEdit, className = '' }: SummaryCardProps) {
  return (
    <div
      className={`bg-white rounded-xl border p-4 relative group hover:border-primary-200 transition-colors ${className}`}
    >
      <button
        onClick={onEdit}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-primary-600"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
          />
        </svg>
      </button>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{emoji}</span>
        <h4 className="font-semibold text-gray-900">{title}</h4>
      </div>
      {children}
    </div>
  )
}
