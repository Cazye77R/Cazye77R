import { useEffect, useState } from 'react'

export default function TerminalText({ text, speed = 30, className = '', onDone }) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    setDisplayed('')
    setDone(false)
    let i = 0
    const id = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) {
        clearInterval(id)
        setDone(true)
        onDone?.()
      }
    }, speed)
    return () => clearInterval(id)
  }, [text, speed, onDone])

  return (
    <span className={className}>
      {displayed}
      {!done && <span className="animate-pulse text-accent-cyan">█</span>}
    </span>
  )
}
