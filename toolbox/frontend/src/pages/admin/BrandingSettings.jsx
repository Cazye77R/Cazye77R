import { useState, useEffect } from 'react'
import { updateBranding } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useBranding } from '../../context/BrandingContext'
import StartupAnimation from '../../components/StartupAnimation'

const THEMES = [
  {
    key: 'hofblick',
    emoji: '🌅',
    name: 'Hofblick',
    desc: 'Alles im Blick',
    subtitle: 'Sonnenaufgang über der Weide',
  },
  {
    key: 'koppel',
    emoji: '🐴',
    name: 'Koppel',
    desc: 'Dein Platz für Tier & Kind',
    subtitle: 'Verspielt & rund',
  },
  {
    key: 'hufspur',
    emoji: '🐾',
    name: 'Hufspur',
    desc: 'Jede Einheit hinterlässt Spuren',
    subtitle: 'Elegant & klar',
  },
  {
    key: 'stallgefluester',
    emoji: '🌙',
    name: 'Stallgeflüster',
    desc: 'Geschichten vom Hof',
    subtitle: 'Abendstimmung & gemütlich',
  },
]

const THEME_DEFAULT_SUBTITLES = {
  hofblick: 'Alles im Blick',
  koppel: 'Dein Platz für Tier & Kind',
  hufspur: 'Jede Einheit hinterlässt Spuren',
  stallgefluester: 'Geschichten vom Hof',
}

export default function BrandingSettings() {
  const { app_name, animation_theme, custom_subtitle, setBranding } = useBranding()
  const [selected, setSelected] = useState(animation_theme || 'hofblick')
  const [customSubtitle, setCustomSubtitle] = useState(custom_subtitle || '')
  const [saving, setSaving] = useState(false)
  const [preview, setPreview] = useState(false)
  const [previewKey, setPreviewKey] = useState(0)
  const toast = useToast()

  useEffect(() => {
    setSelected(animation_theme || 'hofblick')
    setCustomSubtitle(custom_subtitle || '')
  }, [animation_theme, custom_subtitle])

  const currentTheme = THEMES.find(t => t.key === selected) ?? THEMES[0]

  async function handleSave() {
    setSaving(true)
    try {
      const payload = {
        app_name: currentTheme.name,
        animation_theme: selected,
        custom_subtitle: customSubtitle.trim() || null,
      }
      await updateBranding(payload)
      setBranding(prev => ({ ...prev, ...payload }))
      document.title = currentTheme.name
      toast('Branding aktualisiert! Beim nächsten App-Start sichtbar.')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  function handlePreview() {
    setPreviewKey(k => k + 1)
    setPreview(true)
    setTimeout(() => setPreview(false), 4200)
  }

  const previewSubtitle = customSubtitle.trim() || THEME_DEFAULT_SUBTITLES[selected]

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="font-serif text-2xl text-[#2d3b2e] mb-1">Branding & Erscheinungsbild</h1>
        <p className="text-sm text-[#7a9178]">Wähle den Namen und die Startup-Animation für die App.</p>
      </div>

      {/* Theme selection */}
      <div className="bg-white rounded-2xl border border-[#e4ede4] p-6 shadow-sm mb-4">
        <h2 className="text-sm font-semibold text-[#3d4f3e] mb-4">App-Name & Theme</h2>
        <div className="grid grid-cols-2 gap-3">
          {THEMES.map(theme => {
            const active = selected === theme.key
            return (
              <button
                key={theme.key}
                onClick={() => setSelected(theme.key)}
                className={[
                  'relative text-left rounded-xl border-2 p-4 transition-all',
                  active
                    ? 'border-[#5b7c5e] bg-[#eef4ee]'
                    : 'border-[#e4ede4] bg-white hover:border-[#b0d0b2] hover:bg-[#f9fbf9]',
                ].join(' ')}
              >
                {active && (
                  <div className="absolute top-2.5 right-2.5 w-5 h-5 rounded-full bg-[#5b7c5e] flex items-center justify-center">
                    <span className="text-white text-xs">✓</span>
                  </div>
                )}
                <div className="text-2xl mb-2">{theme.emoji}</div>
                <div className="font-semibold text-sm text-[#2d3b2e]">{theme.name}</div>
                <div className="text-xs text-[#7a9178] mt-0.5 leading-snug">{theme.desc}</div>
                <div className="text-[10px] text-[#a8baa9] mt-1 italic">{theme.subtitle}</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Custom subtitle */}
      <div className="bg-white rounded-2xl border border-[#e4ede4] p-6 shadow-sm mb-4">
        <h2 className="text-sm font-semibold text-[#3d4f3e] mb-1">Eigener Untertitel</h2>
        <p className="text-xs text-[#a8baa9] mb-3">Leer lassen für Standard: „{THEME_DEFAULT_SUBTITLES[selected]}"</p>
        <input
          type="text"
          value={customSubtitle}
          onChange={e => setCustomSubtitle(e.target.value)}
          placeholder={`Standard: ${THEME_DEFAULT_SUBTITLES[selected]}`}
          className="w-full px-4 py-2.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] text-sm outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all"
        />
      </div>

      {/* Preview */}
      <div className="bg-white rounded-2xl border border-[#e4ede4] p-6 shadow-sm mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-[#3d4f3e]">Vorschau</h2>
          <button
            onClick={handlePreview}
            className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-[#eef4ee] text-[#5b7c5e] text-sm font-medium hover:bg-[#ddeedd] transition-colors"
          >
            ▶ Vorschau
          </button>
        </div>
        <div
          className="rounded-2xl overflow-hidden border border-[#e4ede4]"
          style={{ height: 300, position: 'relative' }}
        >
          {preview ? (
            <StartupAnimation
              key={previewKey}
              appName={currentTheme.name}
              animationTheme={selected}
              subtitle={previewSubtitle}
              preview
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center bg-[#f5f8f5] text-[#a8baa9] gap-2">
              <span className="text-3xl opacity-40">{currentTheme.emoji}</span>
              <span className="text-sm">Klicke „Vorschau" zum Abspielen</span>
            </div>
          )}
        </div>
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors"
        >
          {saving ? 'Speichern…' : 'Speichern'}
        </button>
      </div>
    </div>
  )
}
