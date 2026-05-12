import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import TerminalText from '../components/TerminalText'

const BOOT_LINES = [
  'MAINFRAME OS v1.0.0',
  'Initializing core systems...',
  'Loading authentication module... OK',
  'Checking database integrity... OK',
  'Starting network interface... OK',
  'System ready.',
]

export default function BootSequence() {
  const navigate = useNavigate()
  const [lineIndex, setLineIndex] = useState(0)
  const [completedLines, setCompletedLines] = useState([])
  const [finished, setFinished] = useState(false)

  useEffect(() => {
    fetch('/auth/setup-required')
      .then((r) => r.json())
      .then((d) => sessionStorage.setItem('setup_required', d.setup_required))
      .catch(() => {})
  }, [])

  function handleLineDone() {
    const current = BOOT_LINES[lineIndex]
    const next = lineIndex + 1

    if (next < BOOT_LINES.length) {
      setCompletedLines((prev) => [...prev, current])
      setLineIndex(next)
    } else {
      setCompletedLines((prev) => [...prev, current])
      setFinished(true)
      setTimeout(() => {
        const setupRequired = sessionStorage.getItem('setup_required')
        navigate(setupRequired === 'true' ? '/setup' : '/login')
      }, 800)
    }
  }

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center p-8">
      <div className="w-full max-w-2xl">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="font-heading text-accent-cyan text-2xl mb-8 tracking-widest"
        >
          MAINFRAME
        </motion.div>

        <div className="space-y-1 font-mono text-sm">
          {completedLines.map((line, i) => (
            <div key={i} className="flex gap-2 text-text-muted">
              <span className="text-accent-green">{'>'}</span>
              <span>{line}</span>
            </div>
          ))}

          {!finished && (
            <div className="flex gap-2">
              <span className="text-accent-green">{'>'}</span>
              <TerminalText
                key={lineIndex}
                text={BOOT_LINES[lineIndex]}
                speed={25}
                onDone={handleLineDone}
                className="text-text-primary"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
