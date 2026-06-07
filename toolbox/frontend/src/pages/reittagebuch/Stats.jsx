import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Legend,
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { getStats } from '../../lib/api'
import { useToast } from '../../context/ToastContext'

export default function Stats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [von, setVon] = useState('')
  const [bis, setBis] = useState('')
  const toast = useToast()

  useEffect(() => {
    setLoading(true)
    const params = {}
    if (von) params.von = von
    if (bis) params.bis = bis
    getStats(params)
      .then(setStats)
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false))
  }, [von, bis])

  return (
    <div className="space-y-7">
      {/* Zeitraum-Filter */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className={lbl}>Von</label>
          <input type="date" value={von} onChange={e => setVon(e.target.value)} className={inp} />
        </div>
        <div>
          <label className={lbl}>Bis</label>
          <input type="date" value={bis} onChange={e => setBis(e.target.value)} className={inp} />
        </div>
        {(von || bis) && (
          <button
            onClick={() => { setVon(''); setBis('') }}
            className="px-3 py-2 text-sm text-[#7a9178] hover:text-[#5b7c5e] transition-colors"
          >
            Zurücksetzen
          </button>
        )}
      </div>

      {loading || !stats ? (
        <Spinner />
      ) : (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Einheiten gesamt"
              value={stats.gesamt_einheiten}
              color="#5b7c5e"
              bg="#eef4ee"
            />
            <StatCard
              label="⌀ Kinder / Woche"
              value={stats.wochen_durchschnitt.kinder}
              color="#2a7ab5"
              bg="#eff6ff"
            />
            <StatCard
              label="⌀ Jugendliche / Woche"
              value={stats.wochen_durchschnitt.jugendliche}
              color="#7c3aed"
              bg="#f5f3ff"
            />
            <StatCard
              label="⌀ Einheiten / Woche"
              value={stats.wochen_durchschnitt.gesamt}
              color="#b45309"
              bg="#fef9f0"
            />
          </div>

          {/* Einsätze pro Tier */}
          {stats.tiere_einsaetze.length > 0 && (
            <ChartCard title="Einsätze pro Tier">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={stats.tiere_einsaetze.map(t => ({
                    name: `${t.emoji} ${t.name}`,
                    Einsätze: t.anzahl,
                  }))}
                  margin={{ top: 4, right: 16, left: -16, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#7a9178' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#7a9178' }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: '12px', border: '1px solid #e4ede4', fontSize: 13 }}
                  />
                  <Bar dataKey="Einsätze" fill="#5b7c5e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          {/* Verlauf pro Woche */}
          {stats.wochen_verlauf.length > 0 && (
            <ChartCard title="Teilnehmer pro Woche">
              <ResponsiveContainer width="100%" height={240}>
                <LineChart
                  data={stats.wochen_verlauf}
                  margin={{ top: 4, right: 16, left: -16, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f4f0" />
                  <XAxis dataKey="kw" tick={{ fontSize: 11, fill: '#7a9178' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#7a9178' }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: '12px', border: '1px solid #e4ede4', fontSize: 13 }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 13, paddingTop: 8 }}
                    formatter={(val) => (
                      <span style={{ color: val === 'kinder' ? '#2a7ab5' : '#7c3aed' }}>
                        {val === 'kinder' ? 'Kinder' : 'Jugendliche'}
                      </span>
                    )}
                  />
                  <Line
                    type="monotone"
                    dataKey="kinder"
                    stroke="#2a7ab5"
                    strokeWidth={2}
                    dot={{ r: 4, fill: '#2a7ab5' }}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="jugendliche"
                    stroke="#7c3aed"
                    strokeWidth={2}
                    dot={{ r: 4, fill: '#7c3aed' }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          {stats.gesamt_einheiten === 0 && (
            <div className="text-center py-16 text-[#a8baa9]">
              <div className="text-4xl mb-3 opacity-30">📊</div>
              <p>Noch keine Daten für diesen Zeitraum.</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function StatCard({ label, value, color, bg }) {
  return (
    <div
      className="rounded-2xl border border-[#e4ede4] p-5 shadow-sm"
      style={{ background: bg }}
    >
      <p className="text-xs font-medium text-[#7a9178] mb-1">{label}</p>
      <p className="text-3xl font-bold leading-none" style={{ color }}>
        {typeof value === 'number' && !Number.isInteger(value)
          ? value.toFixed(1)
          : value}
      </p>
    </div>
  )
}

function ChartCard({ title, children }) {
  return (
    <div className="bg-white rounded-2xl border border-[#e4ede4] p-6 shadow-sm">
      <h3 className="text-sm font-semibold text-[#3d4f3e] mb-4">{title}</h3>
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

const lbl = 'block text-xs font-medium text-[#7a9178] mb-1'
const inp = 'px-3 py-2 rounded-xl border border-[#d4e2d5] bg-white text-sm text-[#2d3b2e] outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all'
