import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getUsers, deleteUser, updateUser } from '../lib/api'

export default function AdminUsers() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  async function toggleActive(u) {
    try {
      const updated = await updateUser(u.id, { is_active: !u.is_active })
      setUsers(prev => prev.map(x => x.id === u.id ? updated : x))
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDelete(u) {
    if (!confirm(`Benutzer „${u.username}" wirklich löschen?`)) return
    try {
      await deleteUser(u.id)
      setUsers(prev => prev.filter(x => x.id !== u.id))
    } catch (err) {
      setError(err.message)
    }
  }

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-[#faf8f4]">
      {/* Top bar */}
      <header className="bg-white border-b border-[#e8ede8] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/dashboard')} className="text-2xl select-none hover:opacity-70 transition-opacity">🧰</button>
          <span className="font-serif text-xl text-[#2d3b2e] tracking-tight">Toolbox</span>
          <span className="text-[#c8d8c9]">/</span>
          <span className="text-sm text-[#5b7c5e] font-medium">Benutzerverwaltung</span>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-sm font-medium text-[#2d3b2e]">{user?.display_name}</p>
          <button onClick={handleLogout} className="text-sm text-[#a8baa9] hover:text-[#5b7c5e] transition-colors">
            Abmelden
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="font-serif text-3xl text-[#2d3b2e] mb-8">Benutzer</h2>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            ⚠️ {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-[#5b7c5e] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="rounded-2xl bg-white border border-[#e8ede8] overflow-hidden"
            style={{ boxShadow: '0 2px 12px rgba(60,80,62,0.06)' }}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e8ede8] bg-[#f5f8f5]">
                  <th className="text-left px-5 py-3 text-[#5b7c5e] font-medium">Name</th>
                  <th className="text-left px-5 py-3 text-[#5b7c5e] font-medium">Username</th>
                  <th className="text-left px-5 py-3 text-[#5b7c5e] font-medium">Rolle</th>
                  <th className="text-left px-5 py-3 text-[#5b7c5e] font-medium">Status</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="border-b border-[#f0f4f0] last:border-0 hover:bg-[#faf8f4] transition-colors">
                    <td className="px-5 py-3 font-medium text-[#2d3b2e]">{u.display_name}</td>
                    <td className="px-5 py-3 text-[#7a9178]">{u.username}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${u.is_admin ? 'bg-[#eef4ee] text-[#5b7c5e]' : 'bg-[#f5f5f5] text-[#9a9a9a]'}`}>
                        {u.is_admin ? 'Admin' : 'User'}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => toggleActive(u)}
                        disabled={u.id === user?.id}
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium transition-colors ${u.is_active ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-red-50 text-red-600 hover:bg-red-100'} disabled:opacity-40 disabled:cursor-not-allowed`}
                      >
                        {u.is_active ? 'Aktiv' : 'Inaktiv'}
                      </button>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => handleDelete(u)}
                        disabled={u.id === user?.id}
                        className="text-xs text-red-400 hover:text-red-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        Löschen
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
