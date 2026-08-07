/**
 * Step 2: Genre & Ton
 */

import { useQuizStore } from '../../../store/quiz'

const genres = [
  { id: 'literary', name: 'Literarisch', icon: '📚' },
  { id: 'thriller', name: 'Thriller', icon: '🔪' },
  { id: 'romance', name: 'Romantik', icon: '💕' },
  { id: 'fantasy', name: 'Fantasy', icon: '🐉' },
  { id: 'scifi', name: 'Science Fiction', icon: '🚀' },
  { id: 'mystery', name: 'Krimi', icon: '🔍' },
  { id: 'horror', name: 'Horror', icon: '👻' },
  { id: 'historical', name: 'Historisch', icon: '⏳' },
]

const subGenres = [
  'Psychologisch',
  'Coming-of-Age',
  'Familiensaga',
  'Dystopie',
  'Urban',
  'Dark',
  'Cozy',
  'Episch',
  'Erotisch',
  'Satirisch',
  'Magischer Realismus',
  'Noir',
]

export default function GenreStep() {
  const { genre, updateGenre } = useQuizStore()

  const handleGenreSelect = (genreId: string) => {
    updateGenre({ primaryGenre: genreId })
  }

  const toggleSubGenre = (subGenre: string) => {
    const newSubGenres = genre.subGenres.includes(subGenre)
      ? genre.subGenres.filter((g) => g !== subGenre)
      : [...genre.subGenres, subGenre].slice(0, 3) // Max 3
    updateGenre({ subGenres: newSubGenres })
  }

  return (
    <div className="space-y-8">
      <div className="text-center max-w-2xl mx-auto">
        <h3 className="text-xl font-medium text-gray-900 mb-2">
          In welchem Genre erzählst du?
        </h3>
        <p className="text-gray-600">
          Wähle ein Hauptgenre und bis zu 3 Sub-Genres.
        </p>
      </div>

      {/* Primary genre */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Hauptgenre
        </label>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {genres.map((g) => (
            <button
              key={g.id}
              onClick={() => handleGenreSelect(g.id)}
              className={`
                p-3 rounded-lg border-2 text-center transition-all
                ${
                  genre.primaryGenre === g.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <span className="text-2xl block mb-1">{g.icon}</span>
              <span className="text-sm font-medium">{g.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Sub-genres */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Sub-Genres (max. 3)
        </label>
        <div className="flex flex-wrap gap-2">
          {subGenres.map((sg) => (
            <button
              key={sg}
              onClick={() => toggleSubGenre(sg)}
              className={`
                px-4 py-2 rounded-full text-sm font-medium transition-all
                ${
                  genre.subGenres.includes(sg)
                    ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-200'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              `}
            >
              {sg}
            </button>
          ))}
        </div>
      </div>

      {/* Tone sliders */}
      <div className="space-y-6 max-w-xl mx-auto">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-600">Dunkel</span>
            <span className="text-gray-600">Hell</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={genre.toneDark}
            onChange={(e) => updateGenre({ toneDark: parseInt(e.target.value) })}
            className="w-full h-2 bg-gradient-to-r from-gray-800 to-yellow-300 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-600">Ernst</span>
            <span className="text-gray-600">Spielerisch</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={genre.toneSerious}
            onChange={(e) => updateGenre({ toneSerious: parseInt(e.target.value) })}
            className="w-full h-2 bg-gradient-to-r from-gray-600 to-pink-400 rounded-lg appearance-none cursor-pointer"
          />
        </div>
      </div>
    </div>
  )
}
