import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Dashboard() {
  const { user, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-[#faf8f4]">
      {/* Top bar */}
      <header className="bg-white border-b border-[#e8ede8] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl select-none">🧰</span>
          <span className="font-serif text-xl text-[#2d3b2e] tracking-tight">Toolbox</span>
        </div>
        <div className="flex items-center gap-4">
          {isAdmin && (
            <button
              onClick={() => navigate('/admin/users')}
              className="text-sm text-[#5b7c5e] font-medium hover:underline"
            >
              Benutzerverwaltung
            </button>
          )}
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium text-[#2d3b2e] leading-none">{user?.display_name}</p>
              <p className="text-xs text-[#7a9178] mt-0.5">{user?.username}{user?.is_admin ? ' · Admin' : ''}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-sm text-[#a8baa9] hover:text-[#5b7c5e] transition-colors"
            >
              Abmelden
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        <h2 className="font-serif text-3xl text-[#2d3b2e] mb-2">
          Hallo, {user?.display_name} 👋
        </h2>
        <p className="text-[#7a9178] mb-10">Willkommen im Toolbox-Dashboard.</p>

        <div className="rounded-2xl bg-white border border-[#e8ede8] p-8 text-center"
          style={{ boxShadow: '0 2px 12px rgba(60,80,62,0.06)' }}>
          <p className="text-[#a8baa9] text-sm">Hier kommen bald deine Tools hin.</p>
        </div>
      </main>
    </div>
  )
}
