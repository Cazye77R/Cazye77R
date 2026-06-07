import { NavLink, Outlet } from 'react-router-dom'

const TABS = [
  { to: '/reittagebuch/neu',          label: 'Neuer Eintrag' },
  { to: '/reittagebuch/uebersicht',   label: 'Übersicht' },
  { to: '/reittagebuch/auswertungen', label: 'Auswertungen' },
  { to: '/reittagebuch/tiere',        label: 'Tiere' },
  { to: '/reittagebuch/export',       label: 'Export' },
]

export default function ReittagebuchLayout() {
  return (
    <div className="max-w-5xl">
      {/* Page header */}
      <div className="mb-1">
        <h1 className="font-serif text-[1.9rem] text-[#2d3b2e] leading-tight">
          🐴 Reittagebuch
        </h1>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-0 border-b border-[#dceadd] mt-4 mb-7 overflow-x-auto">
        {TABS.map(tab => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              [
                'px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors',
                isActive
                  ? 'border-[#5b7c5e] text-[#5b7c5e]'
                  : 'border-transparent text-[#7a9178] hover:text-[#3d4f3e] hover:border-[#c8d8c9]',
              ].join(' ')
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  )
}
