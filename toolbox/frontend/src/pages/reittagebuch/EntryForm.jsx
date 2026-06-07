import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, X } from 'lucide-react'
import { getTiere, createTier, getEintrag, createEintrag, updateEintrag } from '../../lib/api'
import { useToast } from '../../context/ToastContext'

const today = () => new Date().toISOString().split('T')[0]

const EMPTY_FORM = {
  datum: today(),
  aktivitaet: '',
  besonderheiten: '',
  anpassungen: '',
  anzahl_kinder: 0,
  anzahl_jugendliche: 0,
}

export default function EntryForm() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [selectedIds, setSelectedIds] = useState([])
  const [tiere, setTiere] = useState([])
  const [showNewTier, setShowNewTier] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(false)
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const editId = searchParams.get('id')

  // Load tiere
  useEffect(() => {
    getTiere().then(setTiere).catch(() => {})
  }, [])

  // Edit mode: load entry
  useEffect(() => {
    if (!editId) return
    setLoading(true)
    getEintrag(editId)
      .then(e => {
        setForm({
          datum: e.datum,
          aktivitaet: e.aktivitaet,
          besonderheiten: e.besonderheiten ?? '',
          anpassungen: e.anpassungen ?? '',
          anzahl_kinder: e.anzahl_kinder,
          anzahl_jugendliche: e.anzahl_jugendliche,
        })
        setSelectedIds(e.tiere.map(t => t.id))
      })
      .catch(() => toast('Eintrag nicht gefunden', 'error'))
      .finally(() => setLoading(false))
  }, [editId])

  function set(k) {
    return (e) => setForm(f => ({ ...f, [k]: e.target.value }))
  }

  function toggleTier(id) {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.aktivitaet.trim()) {
      toast('Aktivität darf nicht leer sein', 'error')
      return
    }
    setSaving(true)
    try {
      const payload = {
        ...form,
        anzahl_kinder: Number(form.anzahl_kinder),
        anzahl_jugendliche: Number(form.anzahl_jugendliche),
        tier_ids: selectedIds,
      }
      if (editId) {
        await updateEintrag(editId, payload)
        toast('Eintrag gespeichert ✓')
        navigate('/reittagebuch/uebersicht')
      } else {
        await createEintrag(payload)
        toast('Eintrag gespeichert ✓')
        setForm({ ...EMPTY_FORM, datum: today() })
        setSelectedIds([])
      }
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />

  const activeTiere = tiere.filter(t => t.aktiv)

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
      {editId && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-[#7a9178]">Eintrag bearbeiten</p>
          <button
            type="button"
            onClick={() => navigate('/reittagebuch/uebersicht')}
            className="text-sm text-[#a8baa9] hover:text-[#5b7c5e] transition-colors"
          >
            ← Zurück zur Übersicht
          </button>
        </div>
      )}

      {/* Datum */}
      <Field label="Datum" required>
        <input
          type="date"
          value={form.datum}
          onChange={set('datum')}
          required
          className={inputCls}
        />
      </Field>

      {/* Tier-Auswahl */}
      <div>
        <label className={labelCls}>Tiere</label>
        <div className="flex flex-wrap gap-2 mt-1.5">
          {activeTiere.map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => toggleTier(t.id)}
              className={[
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                selectedIds.includes(t.id)
                  ? 'bg-[#5b7c5e] text-white shadow-sm'
                  : 'bg-[#eef4ee] text-[#5b7c5e] hover:bg-[#ddeedd]',
              ].join(' ')}
            >
              <span>{t.emoji}</span>
              <span>{t.name}</span>
            </button>
          ))}

          {/* "+ Neues Tier" chip */}
          {showNewTier ? (
            <NewTierInline
              onCreated={tier => {
                setTiere(prev => [...prev, tier])
                setSelectedIds(prev => [...prev, tier.id])
                setShowNewTier(false)
              }}
              onClose={() => setShowNewTier(false)}
            />
          ) : (
            <button
              type="button"
              onClick={() => setShowNewTier(true)}
              className="flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium border-2 border-dashed border-[#c8d8c9] text-[#7a9178] hover:border-[#5b7c5e] hover:text-[#5b7c5e] transition-colors"
            >
              <Plus size={13} /> Neues Tier
            </button>
          )}
        </div>
      </div>

      {/* Aktivität */}
      <Field label="Aktivität" required>
        <textarea
          value={form.aktivitaet}
          onChange={set('aktivitaet')}
          required
          rows={3}
          placeholder="Was wurde heute gemacht?"
          className={`${inputCls} resize-y`}
        />
      </Field>

      {/* Besonderheiten */}
      <Field label="Besonderheiten">
        <textarea
          value={form.besonderheiten}
          onChange={set('besonderheiten')}
          rows={2}
          placeholder="Auffälligkeiten, besondere Momente…"
          className={`${inputCls} resize-y`}
        />
      </Field>

      {/* Anpassungen */}
      <Field label="Anpassungen fürs nächste Mal">
        <textarea
          value={form.anpassungen}
          onChange={set('anpassungen')}
          rows={2}
          placeholder="Was soll beim nächsten Mal anders sein?"
          className={`${inputCls} resize-y`}
        />
      </Field>

      {/* Teilnehmer */}
      <div className="grid grid-cols-2 gap-4">
        <Field label="Anzahl Kinder">
          <CountInput
            value={form.anzahl_kinder}
            onChange={v => setForm(f => ({ ...f, anzahl_kinder: v }))}
            color="#2a7ab5"
          />
        </Field>
        <Field label="Anzahl Jugendliche">
          <CountInput
            value={form.anzahl_jugendliche}
            onChange={v => setForm(f => ({ ...f, anzahl_jugendliche: v }))}
            color="#7c3aed"
          />
        </Field>
      </div>

      {/* Submit */}
      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={saving}
          className="px-6 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors"
        >
          {saving ? 'Speichern…' : editId ? 'Änderungen speichern' : 'Eintrag speichern'}
        </button>
        {!editId && (
          <button
            type="button"
            onClick={() => { setForm({ ...EMPTY_FORM, datum: today() }); setSelectedIds([]) }}
            className="px-4 py-2.5 rounded-xl border border-[#d4e2d5] text-sm text-[#7a9178] hover:bg-[#f5f8f5] transition-colors"
          >
            Zurücksetzen
          </button>
        )}
      </div>
    </form>
  )
}

// ── Inline "Neues Tier" Dialog ────────────────────────────────────

function NewTierInline({ onCreated, onClose }) {
  const [name, setName] = useState('')
  const [typ, setTyp] = useState('Pferd')
  const [emoji, setEmoji] = useState('🐴')
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  async function handleCreate() {
    if (!name.trim()) return
    setSaving(true)
    try {
      const tier = await createTier({ name: name.trim(), typ, emoji })
      onCreated(tier)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-2xl border-2 border-[#5b7c5e] bg-white shadow-sm flex-wrap">
      <input
        value={emoji}
        onChange={e => setEmoji(e.target.value)}
        className="w-8 text-center bg-transparent border-none outline-none text-base"
        maxLength={2}
        autoFocus
      />
      <input
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Name"
        className="w-20 text-sm bg-transparent border-none outline-none text-[#2d3b2e] placeholder-[#c0cfc1]"
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreate() } }}
      />
      <select
        value={typ}
        onChange={e => setTyp(e.target.value)}
        className="text-xs text-[#7a9178] bg-transparent border-none outline-none cursor-pointer"
      >
        {['Pferd', 'Pony', 'Esel', 'Maultier'].map(o => <option key={o}>{o}</option>)}
      </select>
      <button
        type="button"
        onClick={handleCreate}
        disabled={saving || !name.trim()}
        className="text-xs text-white bg-[#5b7c5e] px-2 py-0.5 rounded-full hover:bg-[#4a6b4d] disabled:opacity-50 transition-colors"
      >
        {saving ? '…' : 'OK'}
      </button>
      <button type="button" onClick={onClose} className="text-[#c0cfc1] hover:text-[#7a9178]">
        <X size={13} />
      </button>
    </div>
  )
}

// ── Count Input ───────────────────────────────────────────────────

function CountInput({ value, onChange, color }) {
  const v = Number(value) || 0
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => onChange(Math.max(0, v - 1))}
        className="w-8 h-8 rounded-lg border border-[#d4e2d5] text-[#5b7c5e] font-bold hover:bg-[#eef4ee] transition-colors flex items-center justify-center text-lg leading-none"
      >
        −
      </button>
      <input
        type="number"
        min="0"
        max="999"
        value={v}
        onChange={e => onChange(Math.max(0, parseInt(e.target.value) || 0))}
        className="w-14 text-center py-1.5 rounded-lg border border-[#d4e2d5] bg-[#faf8f4] text-sm font-semibold outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20"
        style={{ color }}
      />
      <button
        type="button"
        onClick={() => onChange(v + 1)}
        className="w-8 h-8 rounded-lg border border-[#d4e2d5] text-[#5b7c5e] font-bold hover:bg-[#eef4ee] transition-colors flex items-center justify-center text-lg leading-none"
      >
        +
      </button>
    </div>
  )
}

// ── Primitives ────────────────────────────────────────────────────

const labelCls = 'block text-sm font-medium text-[#3d4f3e] mb-1.5'
const inputCls = 'w-full px-4 py-2.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] placeholder-[#b0c4b1] text-sm outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all'

function Field({ label, required, children }) {
  return (
    <div>
      <label className={labelCls}>
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-7 h-7 border-4 border-[#5b7c5e] border-t-transparent rounded-full animate-spin" />
    </div>
  )
}
