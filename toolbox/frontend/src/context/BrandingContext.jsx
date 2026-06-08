import { createContext, useContext, useState, useEffect } from 'react'
import { getBranding } from '../lib/api'

const DEFAULTS = {
  app_name: 'Hofblick',
  animation_theme: 'hofblick',
  custom_subtitle: null,
}

const BrandingContext = createContext(DEFAULTS)

export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULTS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getBranding()
      .then(setBranding)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!loading) {
      document.title = branding.app_name
    }
  }, [branding.app_name, loading])

  return (
    <BrandingContext.Provider value={{ ...branding, loading, setBranding }}>
      {children}
    </BrandingContext.Provider>
  )
}

export function useBranding() {
  return useContext(BrandingContext)
}
