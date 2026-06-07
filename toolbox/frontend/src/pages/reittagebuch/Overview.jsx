import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Pencil, Trash2, X } from 'lucide-react'
import { getEintraege, deleteEintrag, getTiere } from '../../lib/api'
import { useToast } from '../../context/ToastContext'

function fmt(dateStr) {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-')
  return `${d}.${m}.${y}`
}

export default function Overview() {
  const [eintraege, setEintraege] = useState([])
  const [tiere, setTiere] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleteId, setDeleteId] = useState(null)
  const [filters, setFilters] = useState({ von: '', bis: '', tier_id: '' })
  const toast = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    getTiere().then(setTiere).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = {}
    if (filters.von)     params.von     = filters.von
    if (filters.bis)     params.bis     = filters.bis
    if (filters.tier_id) params.tier_id = filters.tier_id
    getEintraege({ ...params, limit: 500 })
      .then(setEintraege)
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false))
  }, [filters])

  async function handleDelete() {
    try {
      await deleteEintrag(deleteId)
      setEintraege(prev => prev.filter(e => e.id !== deleteId))
      toast('Eintrag gelöscht')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setDeleteId(null)
    }
  }

  const setFilter = k => e => setFilters(f => ({ ...f, [k]: e.target.value }))
  const hasFilters = filters.von || filters.bis || filters.tier_id
  const deleteTarget = eintraege.find(e => e.id === deleteId)

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 mb-5 items-end">
        <div>
          <label className={lbl}>Von</label>
          <input type="date" value={filters.von} onChange={setFilter('von')} className={inp} />
        </div>
        <div>
          <label className={lbl}>Bis</label>
          <input type="date" value={filters.bis} onChange={setFilter('bis')} className={inp} />
        </div>
        <div>
          <label className={lbl}>Tier</label>
          <select value={filters.tier_id} onChange={setFilter('tier_id')} className={inp}>
            <option value="">Alle Tiere</option>
            {tiere.map(t => (
              <option key={t.id} value={t.id}>{t.emoji} {t.name}</option>
            ))}
          </select>
        </div>
        {hasFilters && (
          <button
            onClick={() => setFilters({ von: '', bis: '', tier_id: '' })}
            className="flex items-center gap-1 px-3 py-2 text-sm text-[#7a9178] hover:text-[#5b7c5e] transition-colors"
          >
            <X size={14} /> Filter zurücksetzen
          </button>
        )}
        <p className="ml-auto text-sm text-[#a8baa9] self-end pb-2">
          {eintraege.length} {eintraege.length === 1 ? 'Eintrag' : 'Einträge'}
        </p>
      </div>

      {/* Table */}
      {loading ? (
        <Spinner />
      ) : eintraege.length === 0 ? (
        <EmptyState hasFilters={hasFilters} onNew={() => navigate('/reittagebuch/neu')} />
      ) : (
        <div className="bg-white rounded-2xl border border-[#e4ede4] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[700px]">
              <thead>
                <tr className="bg-[#f5f8f5] border-b border-[#e8ede8]">
                  {['Datum', 'Tiere', 'Aktivität', 'Kinder', 'Jugendliche', 'Besonderheiten', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-[10px] font-semibold text-[#7a9178] uppercase tracking-widest whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f0f4f0]">
                {eintraege.map(e => (
                  <tr key={e.id} className="hover:bg-[#fdfaf8] transition-colors align-top">
                    <td className="px-4 py-3 text-[#2d3b2e] font-medium whitespace-nowrap">
                      {fmt(e.datum)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {e.tiere.map(t => (
                          <span
                            key={t.id}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-[#eef4ee] text-[#4a6b4d]"
                          >
                            {t.emoji} {t.name}
                          </span>
                        ))}
                        {e.tiere.length === 0 && <span className="text-[#c0cfc1] text-xs">—</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[#3d4f3e] max-w-[180px]">
                      <p className="line-clamp-2">{e.aktivitaet}</p>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <KidsBadge value={e.anzahl_kinder} color="blue" />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <KidsBadge value={e.anzahl_jugendliche} color="purple" />
                    </td>
                    <td className="px-4 py-3 text-[#7a9178] max-w-[160px]">
                      <p className="line-clamp-2 text-xs">{e.besonderheiten || '—'}</p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={() => navigate(`/reittagebuch/neu?id=${e.id}`)}
                          className="p-1.5 rounded-lg text-[#c0cfc1] hover:text-[#5b7c5e] hover:bg-[#eef4ee] transition-colors"
                          title="Bearbeiten"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          onClick={() => setDeleteId(e.id)}
                          className="p-1.5 rounded-lg text-[#c0cfc1] hover:text-red-500 hover:bg-red-50 transition-colors"
                          title="Löschen"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {deleteId && (
        <ConfirmModal
          message={`Eintrag vom ${fmt(deleteTarget?.datum)} wirklich löschen?`}
          onConfirm={handleDelete}
          onCancel={() => setDeleteId(null)}
        />
      )}
    </div>
  )
}

function KidsBadge({ value, color }) {
  if (!value) return <span className="text-[#c0cfc1] text-xs">—</span>
  const cls = color === 'blue'
    ? 'bg-blue-50 text-blue-700'
    : 'bg-purple-50 text-purple-700'
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {value}
    </span>
  )
}

function EmptyState({ hasFilters, onNew }) {
  return (
    <div className="text-center py-20 bg-white rounded-2xl border border-[#e4ede4]">
      <div className="text-5xl mb-4 opacity-30">🐴</div>
      {hasFilters ? (
        <p className="text-[#a8baa9]">Keine Einträge für diesen Zeitraum / Filter.</p>
      ) : (
        <>
          <p className="text-[#7a9178] font-medium mb-1">Noch keine Einträge</p>
          <p className="text-[#a8baa9] text-sm mb-5">Starte mit deinem ersten Eintrag!</p>
          <button
            onClick={onNew}
            className="px-5 py-2 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] transition-colors"
          >
            Ersten Eintrag anlegen
          </button>
        </>
      )}
    </div>
  )
}

function ConfirmModal({ message, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <p className="text-sm text-[#3d4f3e] mb-6">{message}</p>
        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 py-2 rounded-xl border border-[#d4e2d5] text-sm text-[#6b7c6c] hover:bg-[#f5f8f5] transition-colors">
            Abbrechen
          </button>
          <button onClick={onConfirm} className="flex-1 py-2 rounded-xl bg-red-500 text-white text-sm font-medium hover:bg-red-600 transition-colors">
            Löschen
          </button>
        </div>
      </div>
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

const lbl = 'block text-xs font-medium text-[#7a9178] mb-1'
const inp = 'px-3 py-2 rounded-xl border border-[#d4e2d5] bg-white text-sm text-[#2d3b2e] outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all'
