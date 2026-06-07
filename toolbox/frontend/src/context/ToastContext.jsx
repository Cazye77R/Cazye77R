import { createContext, useCallback, useContext, useState } from 'react'
import { CheckCircle, XCircle } from 'lucide-react'

const ToastCtx = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const toast = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random()
    setToasts(p => [...p, { id, message, type }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500)
  }, [])

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="fixed bottom-5 right-5 z-[200] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={[
              'flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-medium text-white',
              'animate-in slide-in-from-right-4 fade-in duration-200',
              t.type === 'error' ? 'bg-red-500' : 'bg-[#5b7c5e]',
            ].join(' ')}
          >
            {t.type === 'error'
              ? <XCircle size={16} className="flex-shrink-0" />
              : <CheckCircle size={16} className="flex-shrink-0" />
            }
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() {
  return useContext(ToastCtx)
}
