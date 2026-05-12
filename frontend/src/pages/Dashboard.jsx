import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import GlowButton from '../components/GlowButton'
import { useAuthStore } from '../stores/authStore'

export default function Dashboard() {
  const navigate = useNavigate()
  const { username, logout } = useAuthStore()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-bg-primary p-8">
      <header className="flex items-center justify-between mb-12 border-b border-border pb-4">
        <h1 className="font-heading text-accent-cyan text-xl uppercase tracking-widest">
          MAINFRAME
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-text-muted font-mono text-sm">{username}</span>
          <GlowButton variant="danger" onClick={handleLogout}>
            Logout
          </GlowButton>
        </div>
      </header>

      <motion.main
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-2"
      >
        <p className="font-heading text-text-muted text-lg tracking-widest">DASHBOARD</p>
        <p className="font-mono text-text-muted text-sm">App launcher coming soon...</p>
      </motion.main>
    </div>
  )
}
