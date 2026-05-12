import { AnimatePresence, motion } from 'framer-motion'
import { create } from 'zustand'

const useToastStore = create((set) => ({
  toasts: [],
  add: (message, type = 'info') => {
    const id = Date.now()
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }))
    setTimeout(
      () => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
      4000
    )
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

export const toast = {
  info: (msg) => useToastStore.getState().add(msg, 'info'),
  success: (msg) => useToastStore.getState().add(msg, 'success'),
  error: (msg) => useToastStore.getState().add(msg, 'error'),
  warning: (msg) => useToastStore.getState().add(msg, 'warning'),
}

const TYPE_CLASSES = {
  info: 'border-accent-cyan text-accent-cyan',
  success: 'border-accent-green text-accent-green',
  error: 'border-accent-red text-accent-red',
  warning: 'border-accent-orange text-accent-orange',
}

export default function ToastContainer() {
  const { toasts, remove } = useToastStore()

  return (
    <div className="fixed bottom-6 right-6 flex flex-col gap-2 z-50">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 60 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 60 }}
            onClick={() => remove(t.id)}
            className={`bg-bg-secondary border font-mono text-sm px-4 py-3 cursor-pointer max-w-xs rounded ${TYPE_CLASSES[t.type]}`}
          >
            {t.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
