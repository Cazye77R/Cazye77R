import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getEintraege } from '../lib/api'
import { ChevronRight, ArrowRight } from 'lucide-react'

const TOOLS = [
  {
    emoji: '🐴',
    title: 'Reittagebuch',
    description: 'Einheiten dokumentieren & auswerten',
    href: '/reittagebuch',
    enabled: true,
  },
  {
    emoji: '🖨️',
    title: 'Druckkosten',
    description: '3D-Druck Kalkulation',
    href: '/druckkosten',
    enabled: false,
  },
]

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="max-w-4xl">
      {/* Greeting */}
      <div className="mb-8">
        <h1 className="font-serif text-[2rem] text-[#2d3b2e] leading-tight">
          Hallo, {user?.display_name}! 👋
        </h1>
        <p className="text-[#7a9178] mt-1.5 text-sm">Was möchtest du heute tun?</p>
      </div>

      {/* Tool grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {TOOLS.map(tool => (
          <ToolTile
            key={tool.href}
            {...tool}
            onClick={() => tool.enabled && navigate(tool.href)}
          />
        ))}

        {/* Placeholder tile */}
        <div className="rounded-2xl border-2 border-dashed border-[#d4e2d5] p-6 flex flex-col items-center justify-center text-center min-h-[148px] select-none">
          <span className="text-3xl opacity-30 mb-2">➕</span>
          <p className="text-sm text-[#b0c4b1]">Kommt bald…</p>
        </div>
      </div>

      {/* Recent activity */}
      <RecentActivity navigate={navigate} />
    </div>
  )
}

function RecentActivity({ navigate }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEintraege({ limit: 3 })
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="mt-8 max-w-xl">
        <div className="h-3 w-28 bg-[#eef4ee] rounded animate-pulse mb-3" />
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-white rounded-xl border border-[#e4ede4] animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (entries.length === 0) return null

  return (
    <div className="mt-8 max-w-xl">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-[#7a9178] uppercase tracking-widest">
          Letzte Aktivität
        </h2>
        <button
          onClick={() => navigate('/reittagebuch/uebersicht')}
          className="text-xs text-[#5b7c5e] hover:text-[#4a6b4d] flex items-center gap-1 transition-colors"
        >
          Alle anzeigen <ArrowRight size={11} />
        </button>
      </div>
      <div className="space-y-2">
        {entries.map(e => <ActivityRow key={e.id} entry={e} />)}
      </div>
    </div>
  )
}

function ActivityRow({ entry }) {
  function fmt(s) {
    if (!s) return ''
    const [y, m, d] = s.split('-')
    return `${d}.${m}.${y}`
  }

  return (
    <div className="bg-white rounded-xl border border-[#e4ede4] px-4 py-3 flex items-center gap-3">
      <span className="text-sm font-medium text-[#2d3b2e] w-24 flex-shrink-0 tabular-nums">
        {fmt(entry.datum)}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[#3d4f3e] truncate">{entry.aktivitaet}</p>
        {entry.tiere.length > 0 && (
          <p className="text-xs text-[#a8baa9] mt-0.5 truncate">
            {entry.tiere.map(t => `${t.emoji} ${t.name}`).join(' · ')}
          </p>
        )}
      </div>
      <div className="flex gap-1 flex-shrink-0">
        {entry.anzahl_kinder > 0 && (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700">
            {entry.anzahl_kinder}
          </span>
        )}
        {entry.anzahl_jugendliche > 0 && (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700">
            {entry.anzahl_jugendliche}
          </span>
        )}
      </div>
    </div>
  )
}

function ToolTile({ emoji, title, description, enabled, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={!enabled}
      className={[
        'relative text-left rounded-2xl border p-6 min-h-[148px] w-full transition-all duration-150 group',
        enabled
          ? 'bg-white border-[#dceadd] hover:border-[#5b7c5e] hover:shadow-[0_4px_20px_rgba(91,124,94,0.14)] cursor-pointer'
          : 'bg-[#fafafa] border-[#e8e8e8] cursor-not-allowed',
      ].join(' ')}
    >
      {!enabled && (
        <span className="absolute top-4 right-4 text-[10px] font-semibold bg-[#ececec] text-[#aaaaaa] px-2 py-0.5 rounded-full tracking-wide uppercase">
          Kommt bald
        </span>
      )}

      <div
        className={[
          'text-[2rem] mb-3 leading-none transition-transform duration-150',
          !enabled ? 'grayscale opacity-30' : 'group-hover:scale-110',
        ].join(' ')}
      >
        {emoji}
      </div>

      <h3
        className={[
          'font-semibold text-base mb-1',
          enabled ? 'text-[#2d3b2e]' : 'text-[#b0b0b0]',
        ].join(' ')}
      >
        {title}
      </h3>

      <p className={['text-sm leading-snug', enabled ? 'text-[#7a9178]' : 'text-[#c8c8c8]'].join(' ')}>
        {description}
      </p>

      {enabled && (
        <div className="absolute bottom-5 right-5 flex items-center gap-0.5 text-xs font-medium text-[#5b7c5e] opacity-0 group-hover:opacity-100 transition-opacity duration-150">
          Öffnen <ChevronRight size={13} />
        </div>
      )}
    </button>
  )
}
