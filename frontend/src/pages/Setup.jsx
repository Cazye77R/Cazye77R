import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import GlowButton from '../components/GlowButton'
import TerminalInput from '../components/TerminalInput'
import { toast } from '../components/Toast'
import { useAuthStore } from '../stores/authStore'

const STEPS = ['Welcome', 'Create Admin']

export default function Setup() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [step, setStep] = useState(0)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (password !== confirm) {
      toast.error('Passwords do not match')
      return
    }
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    setLoading(true)
    try {
      const res = await fetch('/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!res.ok) {
        const err = await res.json()
        toast.error(err.detail ?? 'Setup failed')
        return
      }
      const data = await res.json()
      setAuth(data.token, data.username, true)
      toast.success('Admin account created')
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
        <h1 className="font-heading text-accent-cyan text-xl uppercase tracking-widest mb-1">
          MAINFRAME
        </h1>
        <p className="text-text-muted text-xs font-mono mb-6">Initial Setup</p>

        <div className="flex gap-3 mb-8">
          {STEPS.map((s, i) => (
            <div key={i} className="flex-1">
              <div className={`h-0.5 mb-1 ${i <= step ? 'bg-accent-cyan' : 'bg-border'}`} />
              <p className={`text-xs font-mono ${i === step ? 'text-text-primary' : 'text-text-muted'}`}>
                {s}
              </p>
            </div>
          ))}
        </div>

        {step === 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            <p className="text-text-primary font-mono text-sm leading-relaxed">
              No administrator account found. Create one to get started.
            </p>
            <GlowButton onClick={() => setStep(1)} className="w-full">
              Begin Setup
            </GlowButton>
          </motion.div>
        )}

        {step === 1 && (
          <motion.form
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onSubmit={handleSubmit}
            className="space-y-4"
          >
            <TerminalInput
              label="Admin Username"
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
              autoComplete="new-password"
              required
            />
            <TerminalInput
              label="Confirm Password"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              required
            />
            <GlowButton type="submit" disabled={loading} className="w-full">
              {loading ? 'Creating...' : 'Create Admin Account'}
            </GlowButton>
          </motion.form>
        )}
      </motion.div>
    </div>
  )
}
