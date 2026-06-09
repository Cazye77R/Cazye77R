import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Users, LogOut, X, BookOpen, KeyRound, Palette } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useBranding } from '../context/BrandingContext'
import { changePassword } from '../lib/api'
import { useToast } from '../context/ToastContext'

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/reittagebuch', icon: BookOpen, label: 'Hoftagebuch' },
]

export default function Layout() {
  const [showPwDialog, setShowPwDialog] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)
  const { user, logout, isAdmin } = useAuth()
  const { app_name } = useBranding()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen bg-[#f4f6f4]">

      {/* ── Sidebar (md+ only) ── */}
      <aside className="hidden md:flex flex-col w-60 bg-white border-r border-[#e4ede4] sticky top-0 h-screen flex-shrink-0">
        <div className="flex items-center px-5 py-[18px] border-b border-[#f0f4f0]">
          <span className="text-[1.4rem] select-none mr-2.5">🧰</span>
          <span className="font-serif text-[1.25rem] text-[#2d3b2e] tracking-tight leading-none">{app_name}</span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(item => (
            <SidebarLink key={item.to} {...item} />
          ))}
          {isAdmin && (
            <>
              <div className="pt-5 pb-1.5 px-2">
                <p className="text-[10px] font-semibold text-[#b0c4b1] uppercase tracking-widest">Admin</p>
              </div>
              <SidebarLink to="/admin/users" icon={Users} label="Benutzer" />
              <SidebarLink to="/admin/branding" icon={Palette} label="Branding" />
            </>
          )}
        </nav>

        <div className="px-4 py-4 border-t border-[#f0f4f0]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-[#eef4ee] flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-semibold text-[#5b7c5e]">
                {user?.display_name?.[0]?.toUpperCase() ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[#2d3b2e] truncate leading-none">{user?.display_name}</p>
              <p className="text-[11px] text-[#a8baa9] truncate mt-0.5">{user?.username}</p>
            </div>
            <button
              onClick={() => setShowPwDialog(true)}
              title="Passwort ändern"
              className="flex-shrink-0 p-1.5 rounded-lg text-[#c0cfc1] hover:text-[#5b7c5e] hover:bg-[#f0f6f0] transition-colors"
            >
              <KeyRound size={14} />
            </button>
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
        <header className="md:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-[#e4ede4] sticky top-0 z-10">
          <div className="flex items-center gap-2">
            <span className="text-xl select-none">🧰</span>
            <span className="font-serif text-lg text-[#2d3b2e] tracking-tight">{app_name}</span>
          </div>
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(v => !v)}
              className="w-10 h-10 rounded-full bg-[#eef4ee] flex items-center justify-center"
              aria-label="Benutzermenü"
            >
              <span className="text-sm font-semibold text-[#5b7c5e]">
                {user?.display_name?.[0]?.toUpperCase() ?? '?'}
              </span>
            </button>
            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                <div className="absolute right-0 top-12 bg-white rounded-2xl shadow-lg border border-[#e4ede4] w-48 z-50 overflow-hidden">
                  <div className="px-4 py-3 border-b border-[#f0f4f0]">
                    <p className="text-sm font-medium text-[#2d3b2e]">{user?.display_name}</p>
                    <p className="text-xs text-[#a8baa9]">{user?.username}</p>
                  </div>
                  <button
                    onClick={() => { setShowUserMenu(false); setShowPwDialog(true) }}
                    className="w-full flex items-center gap-2.5 px-4 py-3 text-sm text-[#3d4f3e] hover:bg-[#f5f8f5] transition-colors"
                  >
                    <KeyRound size={14} className="text-[#7a9178]" />
                    Passwort ändern
                  </button>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-4 py-3 text-sm text-[#3d4f3e] hover:bg-[#f5f8f5] transition-colors"
                  >
                    <LogOut size={14} className="text-[#7a9178]" />
                    Abmelden
                  </button>
                </div>
              </>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-y-auto pb-24 md:pb-8">
          <Outlet />
        </main>
      </div>

      {/* ── Mobile bottom navigation ── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-[#e4ede4] z-30 flex">
        {NAV_ITEMS.map(item => (
          <BottomNavLink key={item.to} {...item} />
        ))}
        {isAdmin && <BottomNavLink to="/admin/users" icon={Users} label="Benutzer" />}
      </nav>

      {showPwDialog && (
        <PasswordDialog onClose={() => setShowPwDialog(false)} />
      )}
    </div>
  )
}

function SidebarLink({ to, icon: Icon, label, end = false }) {
  return (
    <NavLink
      to={to}
      end={end}
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

function BottomNavLink({ to, icon: Icon, label, end = false }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          'flex-1 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] text-[10px] font-medium transition-colors',
          isActive ? 'text-[#5b7c5e]' : 'text-[#a8baa9]',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={22} strokeWidth={isActive ? 2 : 1.5} />
          <span>{label}</span>
        </>
      )}
    </NavLink>
  )
}

function PasswordDialog({ onClose }) {
  const [form, setForm] = useState({ old_password: '', new_password: '', confirm: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const toast = useToast()

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    if (form.new_password !== form.confirm) {
      setError('Die Passwörter stimmen nicht überein')
      return
    }
    setSaving(true)
    setError('')
    try {
      await changePassword({ old_password: form.old_password, new_password: form.new_password })
      toast('Passwort erfolgreich geändert ✓')
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#f0f4f0]">
          <h2 className="font-semibold text-[#2d3b2e]">Passwort ändern</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg text-[#a8baa9] hover:text-[#5b7c5e] hover:bg-[#eef4ee] transition-colors">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <div>
            <label className={lbl}>Aktuelles Passwort</label>
            <input type="password" value={form.old_password} onChange={set('old_password')} required autoFocus className={inp} />
          </div>
          <div>
            <label className={lbl}>Neues Passwort</label>
            <input type="password" value={form.new_password} onChange={set('new_password')} required className={inp} />
          </div>
          <div>
            <label className={lbl}>Passwort bestätigen</label>
            <input type="password" value={form.confirm} onChange={set('confirm')} required className={inp} />
          </div>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-[#d4e2d5] text-sm text-[#6b7c6c] hover:bg-[#f5f8f5] transition-colors">
              Abbrechen
            </button>
            <button type="submit" disabled={saving} className="flex-1 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors">
              {saving ? 'Speichern…' : 'Ändern'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const lbl = 'block text-sm font-medium text-[#3d4f3e] mb-1.5'
const inp = 'w-full px-4 py-2.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] text-sm outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all'
