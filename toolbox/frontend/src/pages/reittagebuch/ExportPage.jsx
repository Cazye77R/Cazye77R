import { useState } from 'react'
import { Download, Database } from 'lucide-react'
import { downloadExport, downloadBackup } from '../../lib/api'
import { useToast } from '../../context/ToastContext'
import { useAuth } from '../../context/AuthContext'

export default function ExportPage() {
  const [von, setVon] = useState('')
  const [bis, setBis] = useState('')
  const [loadingXlsx, setLoadingXlsx] = useState(false)
  const [loadingDb, setLoadingDb] = useState(false)
  const toast = useToast()
  const { isAdmin } = useAuth()

  async function handleExport() {
    setLoadingXlsx(true)
    try {
      const params = {}
      if (von) params.von = von
      if (bis) params.bis = bis
      await downloadExport(params)
      toast('Excel-Export heruntergeladen ✓')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setLoadingXlsx(false)
    }
  }

  async function handleBackup() {
    setLoadingDb(true)
    try {
      await downloadBackup()
      toast('Datenbank-Backup heruntergeladen ✓')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setLoadingDb(false)
    }
  }

  return (
    <div className="space-y-6 max-w-xl">

      {/* Excel Export */}
      <ExportCard
        icon={<Download size={20} />}
        title="Excel-Export"
        description="Alle Einträge als .xlsx-Datei herunterladen. Optional nach Zeitraum filtern."
        color="#5b7c5e"
        bg="#eef4ee"
      >
        <div className="flex flex-wrap gap-3 mb-4">
          <div>
            <label className={lbl}>Von</label>
            <input type="date" value={von} onChange={e => setVon(e.target.value)} className={inp} />
          </div>
          <div>
            <label className={lbl}>Bis</label>
            <input type="date" value={bis} onChange={e => setBis(e.target.value)} className={inp} />
          </div>
        </div>
        <button
          onClick={handleExport}
          disabled={loadingXlsx}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors"
        >
          <Download size={15} />
          {loadingXlsx ? 'Wird generiert…' : 'Als Excel herunterladen'}
        </button>
      </ExportCard>

      {/* DB Backup — Admin only */}
      {isAdmin && (
        <ExportCard
          icon={<Database size={20} />}
          title="Datenbank-Backup"
          description="Lädt die gesamte SQLite-Datenbank (toolbox.db) als Datei herunter. Enthält alle Daten aller Benutzer."
          color="#b45309"
          bg="#fef9f0"
        >
          <button
            onClick={handleBackup}
            disabled={loadingDb}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#b45309] text-white text-sm font-medium hover:bg-[#92400e] disabled:opacity-60 transition-colors"
          >
            <Database size={15} />
            {loadingDb ? 'Wird heruntergeladen…' : 'Datenbank herunterladen'}
          </button>
        </ExportCard>
      )}
    </div>
  )
}

function ExportCard({ icon, title, description, color, bg, children }) {
  return (
    <div className="bg-white rounded-2xl border border-[#e4ede4] shadow-sm overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#f0f4f0]" style={{ background: bg }}>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: color, color: '#fff' }}>
          {icon}
        </div>
        <h3 className="font-semibold text-[#2d3b2e]">{title}</h3>
      </div>
      <div className="px-6 py-5">
        <p className="text-sm text-[#7a9178] mb-4 leading-relaxed">{description}</p>
        {children}
      </div>
    </div>
  )
}

const lbl = 'block text-xs font-medium text-[#7a9178] mb-1'
const inp = 'px-3 py-2 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-sm text-[#2d3b2e] outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all'
