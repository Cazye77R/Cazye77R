import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#faf8f4] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Branding */}
        <div className="text-center mb-8 select-none">
          <div className="text-6xl mb-3">🧰</div>
          <h1 className="font-serif text-[2rem] leading-none text-[#2d3b2e] tracking-tight">
            Toolbox
          </h1>
          <p className="text-[#7a9178] text-sm mt-2 font-sans">
            Melde dich an, um fortzufahren
          </p>
        </div>

        {/* Card */}
        <div
          className="bg-white rounded-2xl p-8"
          style={{ boxShadow: '0 4px 32px rgba(60,80,62,0.10), 0 1px 4px rgba(60,80,62,0.06)' }}
        >
          <form onSubmit={handleSubmit} className="space-y-5">

            <div>
              <label className="block text-sm font-medium text-[#3d4f3e] mb-1.5">
                Benutzername
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                autoFocus
                autoComplete="username"
                placeholder="admin"
                className="w-full px-4 py-2.5 rounded-lg border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] placeholder-[#b0c4b1] text-sm transition-all outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#3d4f3e] mb-1.5">
                Passwort
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full px-4 py-2.5 rounded-lg border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] placeholder-[#b0c4b1] text-sm transition-all outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-start gap-2">
                <span className="mt-px">⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg font-medium text-sm text-white transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ background: loading ? '#7a9178' : '#5b7c5e' }}
              onMouseEnter={e => { if (!loading) e.target.style.background = '#4a6b4d' }}
              onMouseLeave={e => { if (!loading) e.target.style.background = '#5b7c5e' }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin inline-block" />
                  Anmelden…
                </span>
              ) : 'Anmelden'}
            </button>

          </form>
        </div>

        {/* Footer hint */}
        <p className="text-center text-xs text-[#a8baa9] mt-6">
          Internes Tool · Kein öffentlicher Zugang
        </p>
      </div>
    </div>
  )
}
