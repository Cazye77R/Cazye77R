import { useEffect, useState } from 'react'
import { Plus, X, ChevronDown } from 'lucide-react'
import { getTiere, createTier, updateTier, deleteTier, getStats, getTierTypen, updateTierTypen } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { SkeletonCards } from '../../components/Skeleton'

export default function Animals() {
  const [tiere, setTiere] = useState([])
  const [typen, setTypen] = useState([])
  const [einsaetze, setEinsaetze] = useState({})
  const [loading, setLoading] = useState(true)
  const [editingTier, setEditingTier] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const toast = useToast()

  useEffect(() => {
    Promise.all([getTiere(), getStats(), getTierTypen()])
      .then(([t, s, tp]) => {
        setTiere(t)
        setTypen(tp)
        const map = {}
        s.tiere_einsaetze.forEach(e => { map[e.tier_id] = e.anzahl })
        setEinsaetze(map)
      })
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate(form) {
    const tier = await createTier(form)
    setTiere(prev => [...prev, tier])
    setShowCreate(false)
    toast(`${tier.emoji} ${tier.name} angelegt`)
  }

  async function handleEdit(form) {
    const updated = await updateTier(editingTier.id, form)
    setTiere(prev => prev.map(t => t.id === updated.id ? updated : t))
    setEditingTier(null)
    toast('Tier aktualisiert')
  }

  async function handleDeactivate(tier) {
    await deleteTier(tier.id)
    setTiere(prev => prev.map(t => t.id === tier.id ? { ...t, aktiv: false } : t))
    toast(`${tier.name} deaktiviert`)
  }

  async function handleReactivate(tier) {
    const updated = await updateTier(tier.id, { aktiv: true })
    setTiere(prev => prev.map(t => t.id === updated.id ? updated : t))
    toast(`${tier.name} reaktiviert`)
  }

  if (loading) return <SkeletonCards count={4} />

  const active   = tiere.filter(t => t.aktiv)
  const inactive = tiere.filter(t => !t.aktiv)

  return (
    <div>
      {/* Active animals */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
        {active.map(t => (
          <TierCard
            key={t.id}
            tier={t}
            einsaetze={einsaetze[t.id] ?? 0}
            onEdit={() => setEditingTier(t)}
            onDeactivate={() => handleDeactivate(t)}
          />
        ))}

        <button
          onClick={() => setShowCreate(true)}
          className="rounded-2xl border-2 border-dashed border-[#c8d8c9] p-5 flex flex-col items-center justify-center gap-2 text-[#7a9178] hover:border-[#5b7c5e] hover:text-[#5b7c5e] transition-colors min-h-[140px] cursor-pointer"
        >
          <Plus size={24} strokeWidth={1.5} />
          <span className="text-sm font-medium">Neues Tier</span>
        </button>
      </div>

      {/* Inactive animals */}
      {inactive.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-[#a8baa9] uppercase tracking-widest mb-3">
            Inaktiv
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
            {inactive.map(t => (
              <TierCard
                key={t.id}
                tier={t}
                einsaetze={einsaetze[t.id] ?? 0}
                onEdit={() => setEditingTier(t)}
                onReactivate={() => handleReactivate(t)}
                inactive
              />
            ))}
          </div>
        </div>
      )}

      {/* Tier type management */}
      <TierTypenManager typen={typen} onChange={setTypen} />

      {/* Modals */}
      {showCreate && (
        <TierModal
          title="Neues Tier"
          typen={typen}
          onTypenChange={setTypen}
          onClose={() => setShowCreate(false)}
          onSubmit={handleCreate}
        />
      )}
      {editingTier && (
        <TierModal
          title={`${editingTier.emoji} ${editingTier.name} bearbeiten`}
          initial={editingTier}
          typen={typen}
          onTypenChange={setTypen}
          onClose={() => setEditingTier(null)}
          onSubmit={handleEdit}
        />
      )}
    </div>
  )
}

// ── Tier Type Manager ─────────────────────────────────────────────

function TierTypenManager({ typen, onChange }) {
  const [input, setInput] = useState('')
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function addTyp() {
    const t = input.trim()
    if (!t || typen.includes(t)) return
    const next = [...typen, t]
    setSaving(true)
    try {
      const saved = await updateTierTypen(next)
      onChange(saved)
      setInput('')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  async function removeTyp(typ) {
    if (typen.length <= 1) {
      toast('Mindestens ein Tiertyp muss bestehen bleiben', 'error')
      return
    }
    try {
      const saved = await updateTierTypen(typen.filter(t => t !== typ))
      onChange(saved)
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  return (
    <div className="mt-4">
      <h3 className="text-xs font-semibold text-[#a8baa9] uppercase tracking-widest mb-3">
        Tiertypen
      </h3>
      <div className="bg-white rounded-2xl border border-[#e4ede4] p-4">
        <div className="flex flex-wrap gap-2 mb-3">
          {typen.map(typ => (
            <span key={typ} className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium bg-[#eef4ee] text-[#4a6b4d]">
              {typ}
              <button
                onClick={() => removeTyp(typ)}
                className="ml-0.5 text-[#7a9178] hover:text-red-500 transition-colors"
                title={`${typ} entfernen`}
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTyp() } }}
            placeholder="Neuer Typ…"
            className="flex-1 px-3 py-1.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-sm text-[#2d3b2e] outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all"
          />
          <button
            onClick={addTyp}
            disabled={saving || !input.trim()}
            className="px-3 py-1.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-50 transition-colors flex items-center"
          >
            <Plus size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Tier Card ─────────────────────────────────────────────────────

function TierCard({ tier, einsaetze, onEdit, onDeactivate, onReactivate, inactive }) {
  return (
    <div className={[
      'rounded-2xl border p-5 flex flex-col gap-3 transition-all group relative',
      inactive
        ? 'bg-[#fafafa] border-[#e8e8e8] opacity-60'
        : 'bg-white border-[#e4ede4] hover:border-[#5b7c5e] hover:shadow-[0_4px_16px_rgba(91,124,94,0.10)]',
    ].join(' ')}>
      <div className="text-4xl leading-none select-none">
        {inactive ? <span className="grayscale">{tier.emoji}</span> : tier.emoji}
      </div>

      <div className="flex-1">
        <p className="font-semibold text-[#2d3b2e] text-base leading-tight">{tier.name}</p>
        <p className="text-xs text-[#7a9178] mt-0.5">{tier.typ}</p>
        <p className="text-xs text-[#a8baa9] mt-2">
          {einsaetze} {einsaetze === 1 ? 'Einsatz' : 'Einsätze'} gesamt
        </p>
      </div>

      <div className="flex gap-1.5">
        {!inactive && (
          <button
            onClick={onEdit}
            className="flex-1 py-1.5 rounded-lg text-xs font-medium text-[#5b7c5e] bg-[#eef4ee] hover:bg-[#ddeedd] transition-colors"
          >
            Bearbeiten
          </button>
        )}
        {!inactive && onDeactivate && (
          <button
            onClick={onDeactivate}
            className="py-1.5 px-2 rounded-lg text-xs text-[#c0cfc1] hover:text-red-500 hover:bg-red-50 transition-colors"
            title="Deaktivieren"
          >
            <X size={13} />
          </button>
        )}
        {inactive && onReactivate && (
          <button
            onClick={onReactivate}
            className="flex-1 py-1.5 rounded-lg text-xs font-medium text-[#5b7c5e] bg-[#eef4ee] hover:bg-[#ddeedd] transition-colors"
          >
            Reaktivieren
          </button>
        )}
      </div>
    </div>
  )
}

// ── Emoji Groups ─────────────────────────────────────────────────

const EMOJI_GROUPS = [
  { label: 'Pferde & Esel',   emojis: ['🐴', '🐎', '🦄', '🫏', '🏇'] },
  { label: 'Bauernhof',       emojis: ['🐮', '🐂', '🐄', '🐷', '🐖', '🐑', '🐏', '🐐', '🐓', '🐔', '🐣', '🦆', '🦢', '🐇', '🐰'] },
  { label: 'Hunde & Katzen',  emojis: ['🐕', '🐩', '🐈', '🐾'] },
  { label: 'Wildtiere',       emojis: ['🦌', '🦙', '🦥', '🐢', '🦜', '🦉', '🐝'] },
]

// ── Tier Modal ────────────────────────────────────────────────────

function TierModal({ title, initial, typen, onTypenChange, onClose, onSubmit }) {
  const defaultTyp = typen[0] ?? 'Pferd'
  const [form, setForm] = useState({
    name: initial?.name ?? '',
    typ: initial?.typ ?? defaultTyp,
    emoji: initial?.emoji ?? '🐴',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [newTypInput, setNewTypInput] = useState('')
  const [addingTyp, setAddingTyp] = useState(false)
  const toast = useToast()

  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function handleAddTyp() {
    const t = newTypInput.trim()
    if (!t || typen.includes(t)) { setNewTypInput(''); setAddingTyp(false); return }
    try {
      const saved = await updateTierTypen([...typen, t])
      onTypenChange(saved)
      setForm(f => ({ ...f, typ: t }))
      setNewTypInput('')
      setAddingTyp(false)
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name.trim()) return
    setSaving(true)
    setError('')
    try {
      await onSubmit({ ...form, name: form.name.trim() })
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#f0f4f0]">
          <h2 className="font-serif text-xl text-[#2d3b2e]">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg text-[#a8baa9] hover:text-[#5b7c5e] hover:bg-[#eef4ee] transition-colors">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

          {/* Emoji picker */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-sm font-medium text-[#3d4f3e]">Emoji</label>
              <span className="text-2xl leading-none select-none">{form.emoji}</span>
            </div>
            <div className="rounded-xl border border-[#d4e2d5] bg-[#faf8f4] p-2.5 max-h-44 overflow-y-auto">
              {EMOJI_GROUPS.map(group => (
                <div key={group.label} className="mb-2 last:mb-0">
                  <p className="text-[10px] font-semibold text-[#a8baa9] uppercase tracking-wider mb-1 px-0.5">{group.label}</p>
                  <div className="grid grid-cols-8 gap-0.5">
                    {group.emojis.map(e => (
                      <button
                        key={e} type="button"
                        onClick={() => setForm(f => ({ ...f, emoji: e }))}
                        className={[
                          'w-8 h-8 rounded-lg text-lg flex items-center justify-center transition-all select-none',
                          form.emoji === e ? 'bg-[#5b7c5e]' : 'hover:bg-[#eef4ee]',
                        ].join(' ')}
                      >
                        {e}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs text-[#7a9178]">Eigenes:</span>
              <input
                value={form.emoji}
                onChange={set('emoji')}
                maxLength={2}
                className="w-10 h-8 rounded-lg border border-[#d4e2d5] text-center text-base outline-none focus:border-[#5b7c5e]"
                placeholder="…"
              />
            </div>
          </div>

          <div>
            <label className={lbl}>Name <span className="text-red-400">*</span></label>
            <input
              value={form.name}
              onChange={set('name')}
              required
              autoFocus
              placeholder="z.B. Pollie"
              className={inp}
            />
          </div>

          <div>
            <label className={lbl}>Typ</label>
            <select value={form.typ} onChange={set('typ')} className={inp}>
              {typen.map(t => <option key={t}>{t}</option>)}
            </select>
            {addingTyp ? (
              <div className="flex gap-1.5 mt-1.5">
                <input
                  value={newTypInput}
                  onChange={e => setNewTypInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddTyp() } if (e.key === 'Escape') { setAddingTyp(false); setNewTypInput('') } }}
                  placeholder="Neuer Typ…"
                  autoFocus
                  className="flex-1 px-3 py-1.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-sm text-[#2d3b2e] outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all"
                />
                <button type="button" onClick={handleAddTyp} disabled={!newTypInput.trim()} className="px-3 py-1.5 rounded-xl bg-[#5b7c5e] text-white text-xs font-medium hover:bg-[#4a6b4d] disabled:opacity-50 transition-colors">
                  OK
                </button>
                <button type="button" onClick={() => { setAddingTyp(false); setNewTypInput('') }} className="px-2 py-1.5 rounded-xl text-[#a8baa9] hover:text-[#5b7c5e] transition-colors">
                  <X size={13} />
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => setAddingTyp(true)} className="mt-1.5 text-xs text-[#7a9178] hover:text-[#5b7c5e] transition-colors flex items-center gap-1">
                <Plus size={11} /> Neuen Typ hinzufügen
              </button>
            )}
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-[#d4e2d5] text-sm text-[#6b7c6c] hover:bg-[#f5f8f5] transition-colors">
              Abbrechen
            </button>
            <button type="submit" disabled={saving} className="flex-1 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors">
              {saving ? 'Speichern…' : 'Speichern'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const lbl = 'block text-sm font-medium text-[#3d4f3e] mb-1.5'
const inp = 'w-full px-4 py-2.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] text-sm outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all'
