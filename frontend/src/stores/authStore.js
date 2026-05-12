import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const API = '/auth'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      username: null,
      isAdmin: false,

      setAuth: (token, username, isAdmin = false) =>
        set({ token, username, isAdmin }),

      logout: async () => {
        const { token } = get()
        if (token) {
          try {
            await fetch(`${API}/logout?token=${token}`, { method: 'POST' })
          } catch (_) {}
        }
        set({ token: null, username: null, isAdmin: false })
      },

      checkAuth: async () => {
        const { token } = get()
        if (!token) return
        try {
          const res = await fetch(`${API}/me?token=${token}`)
          if (!res.ok) set({ token: null, username: null, isAdmin: false })
        } catch (_) {
          set({ token: null, username: null, isAdmin: false })
        }
      },
    }),
    { name: 'mainframe-auth' }
  )
)
