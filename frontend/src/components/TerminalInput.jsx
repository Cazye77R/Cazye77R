import { forwardRef } from 'react'

const TerminalInput = forwardRef(function TerminalInput(
  { label, type = 'text', className = '', ...props },
  ref
) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs text-text-muted font-heading uppercase tracking-wider">
          {label}
        </label>
      )}
      <input
        ref={ref}
        type={type}
        className={`
          bg-bg-secondary border border-border text-text-primary
          font-mono text-sm px-3 py-2 rounded outline-none
          focus:border-accent-cyan focus:shadow-cyan
          transition-all duration-200
          ${className}
        `}
        {...props}
      />
    </div>
  )
})

export default TerminalInput
