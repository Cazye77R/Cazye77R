import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import GlowButton from '../components/GlowButton'
import TerminalInput from '../components/TerminalInput'
import { toast } from '../components/Toast'
import { useAuthStore } from '../stores/authStore'

export default function Login() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        const err = await res.json()
        toast.error(err.detail ?? 'Login failed')
        return
      }
      const data = await res.json()
      setAuth(data.token, data.username)
      navigate('/dashboard')
    } catch (_) {
      toast.error('Connection error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md bg-bg-secondary border border-border p-8 rounded"
      >
        <h1 className="font-heading text-accent-cyan text-xl mb-1 uppercase tracking-widest">
          MAINFRAME
        </h1>
        <p className="text-text-muted text-xs font-mono mb-8">Authentication required</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <TerminalInput
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <TerminalInput
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          <GlowButton type="submit" disabled={loading} className="w-full mt-2">
            {loading ? 'Authenticating...' : 'Login'}
          </GlowButton>
        </form>
      </motion.div>
    </div>
  )
}
