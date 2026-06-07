import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ChevronRight } from 'lucide-react'

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
      {/* "Kommt bald" badge */}
      {!enabled && (
        <span className="absolute top-4 right-4 text-[10px] font-semibold bg-[#ececec] text-[#aaaaaa] px-2 py-0.5 rounded-full tracking-wide uppercase">
          Kommt bald
        </span>
      )}

      {/* Emoji icon */}
      <div
        className={[
          'text-[2rem] mb-3 leading-none transition-transform duration-150',
          !enabled ? 'grayscale opacity-30' : 'group-hover:scale-110',
        ].join(' ')}
      >
        {emoji}
      </div>

      {/* Title */}
      <h3
        className={[
          'font-semibold text-base mb-1',
          enabled ? 'text-[#2d3b2e]' : 'text-[#b0b0b0]',
        ].join(' ')}
      >
        {title}
      </h3>

      {/* Description */}
      <p className={['text-sm leading-snug', enabled ? 'text-[#7a9178]' : 'text-[#c8c8c8]'].join(' ')}>
        {description}
      </p>

      {/* Hover CTA */}
      {enabled && (
        <div className="absolute bottom-5 right-5 flex items-center gap-0.5 text-xs font-medium text-[#5b7c5e] opacity-0 group-hover:opacity-100 transition-opacity duration-150">
          Öffnen <ChevronRight size={13} />
        </div>
      )}
    </button>
  )
}
