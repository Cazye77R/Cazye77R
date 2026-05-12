import { motion } from 'framer-motion'

const VARIANTS = {
  primary: 'border-accent-cyan text-accent-cyan hover:bg-accent-cyan/10 shadow-cyan',
  danger: 'border-accent-red text-accent-red hover:bg-accent-red/10',
  success: 'border-accent-green text-accent-green hover:bg-accent-green/10',
}

export default function GlowButton({
  children,
  onClick,
  type = 'button',
  disabled = false,
  variant = 'primary',
  className = '',
}) {
  return (
    <motion.button
      type={type}
      onClick={onClick}
      disabled={disabled}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={`
        bg-transparent border font-heading text-sm uppercase tracking-wider
        px-6 py-2 transition-all duration-200
        disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANTS[variant] ?? VARIANTS.primary}
        ${className}
      `}
    >
      {children}
    </motion.button>
  )
}
