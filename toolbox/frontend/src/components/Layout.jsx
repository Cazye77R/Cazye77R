import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Users, LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', end: true },
]

export default function Layout() {
  const [open, setOpen] = useState(false)
  const { user, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  const close = () => setOpen(false)

  return (
    <div className="flex min-h-screen bg-[#f4f6f4]">

      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/25 z-20 md:hidden"
          onClick={close}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={[
          'fixed top-0 left-0 h-full w-60 bg-white border-r border-[#e4ede4] z-30',
          'flex flex-col transition-transform duration-200 ease-in-out',
          'md:static md:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-5 py-[18px] border-b border-[#f0f4f0]">
          <div className="flex items-center gap-2.5">
            <span className="text-[1.4rem] select-none">🧰</span>
            <span className="font-serif text-[1.25rem] text-[#2d3b2e] tracking-tight leading-none">
              Toolbox
            </span>
          </div>
          {/* Close button (mobile only) */}
          <button
            onClick={close}
            className="md:hidden p-1 rounded-lg text-[#a8baa9] hover:text-[#5b7c5e] hover:bg-[#f0f6f0] transition-colors"
            aria-label="Menü schließen"
          >
            <X size={16} />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(item => (
            <SidebarLink key={item.to} {...item} onClick={close} />
          ))}

          {isAdmin && (
            <>
              <div className="pt-5 pb-1.5 px-2">
                <p className="text-[10px] font-semibold text-[#b0c4b1] uppercase tracking-widest">
                  Admin
                </p>
              </div>
              <SidebarLink
                to="/admin/users"
                icon={Users}
                label="Benutzer"
                onClick={close}
              />
            </>
          )}
        </nav>

        {/* User section */}
        <div className="px-4 py-4 border-t border-[#f0f4f0]">
          <div className="flex items-center gap-2">
            {/* Avatar circle */}
            <div className="w-7 h-7 rounded-full bg-[#eef4ee] flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-semibold text-[#5b7c5e]">
                {user?.display_name?.[0]?.toUpperCase() ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[#2d3b2e] truncate leading-none">
                {user?.display_name}
              </p>
              <p className="text-[11px] text-[#a8baa9] truncate mt-0.5">
                {user?.username}
              </p>
            </div>
            <button
              onClick={handleLogout}
              title="Abmelden"
              className="flex-shrink-0 p-1.5 rounded-lg text-[#c0cfc1] hover:text-[#5b7c5e] hover:bg-[#f0f6f0] transition-colors"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3.5 bg-white border-b border-[#e4ede4] sticky top-0 z-10">
          <button
            onClick={() => setOpen(true)}
            className="p-1.5 rounded-lg text-[#5b7c5e] hover:bg-[#eef4ee] transition-colors"
            aria-label="Menü öffnen"
          >
            <Menu size={20} />
          </button>
          <span className="font-serif text-lg text-[#2d3b2e] tracking-tight">Toolbox</span>
        </header>

        {/* Page content via Outlet */}
        <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function SidebarLink({ to, icon: Icon, label, end = false, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        [
          'flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors',
          isActive
            ? 'bg-[#eef4ee] text-[#4a6b4d]'
            : 'text-[#6b7c6c] hover:bg-[#f5f8f5] hover:text-[#3d4f3e]',
        ].join(' ')
      }
    >
      <Icon size={16} className="flex-shrink-0 opacity-80" />
      {label}
    </NavLink>
  )
}
