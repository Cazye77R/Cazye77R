import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, Shield, ShieldOff, X } from 'lucide-react'
import { getUsers, createUser, updateUser, deleteUser, getUserModules, setUserModules } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const ALL_MODULES = [
  { key: 'hoftagebuch', name: 'Hoftagebuch', emoji: '📖' },
]

export default function UserManagement() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)

  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleCreate(form) {
    const created = await createUser(form)
    setUsers(prev => [...prev, created])
    setShowCreate(false)
  }

  async function handleEdit(form, moduleKeys) {
    const updated = await updateUser(editingUser.id, form)
    await setUserModules(editingUser.id, moduleKeys)
    setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
    setEditingUser(null)
  }

  async function handleDelete() {
    await deleteUser(deleteConfirmId)
    setUsers(prev => prev.filter(u => u.id !== deleteConfirmId))
    setDeleteConfirmId(null)
  }

  const deleteTarget = users.find(u => u.id === deleteConfirmId)

  return (
    <div className="max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-serif text-[2rem] text-[#2d3b2e] leading-tight">Benutzerverwaltung</h1>
          <p className="text-[#7a9178] text-sm mt-1.5">
            {users.length} {users.length === 1 ? 'Benutzer' : 'Benutzer'}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] active:bg-[#3d5a40] transition-colors shadow-sm"
        >
          <Plus size={15} />
          Neuer Benutzer
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-24">
          <div className="w-7 h-7 border-4 border-[#5b7c5e] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-[#e4ede4] overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#f5f8f5] border-b border-[#e8ede8]">
                {['Name', 'Benutzername', 'Rolle', 'Status', 'Erstellt'].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-[10px] font-semibold text-[#7a9178] uppercase tracking-widest">
                    {h}
                  </th>
                ))}
                <th className="px-5 py-3 w-20" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f0f4f0]">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-[#fdfaf8] transition-colors">
                  <td className="px-5 py-3.5 font-medium text-[#2d3b2e]">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-[#eef4ee] flex items-center justify-center flex-shrink-0">
                        <span className="text-xs font-semibold text-[#5b7c5e]">
                          {u.display_name[0]?.toUpperCase()}
                        </span>
                      </div>
                      {u.display_name}
                      {u.id === me?.id && (
                        <span className="text-[10px] text-[#a8baa9] bg-[#f0f4f0] px-1.5 py-0.5 rounded-full">
                          ich
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs text-[#7a9178]">{u.username}</td>
                  <td className="px-5 py-3.5">
                    <Badge
                      active={u.is_admin}
                      activeLabel="Admin"
                      inactiveLabel="User"
                      ActiveIcon={Shield}
                      InactiveIcon={ShieldOff}
                      green={u.is_admin}
                    />
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      u.is_active
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-red-50 text-red-600'
                    }`}>
                      {u.is_active ? 'Aktiv' : 'Inaktiv'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-[#b0c4b1]">
                    {new Date(u.created_at).toLocaleDateString('de-DE')}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-1 justify-end">
                      <IconButton
                        title="Bearbeiten"
                        onClick={() => setEditingUser(u)}
                        icon={<Pencil size={13} />}
                        hoverClass="hover:text-[#5b7c5e] hover:bg-[#eef4ee]"
                      />
                      <IconButton
                        title="Löschen"
                        onClick={() => setDeleteConfirmId(u.id)}
                        disabled={u.id === me?.id}
                        icon={<Trash2 size={13} />}
                        hoverClass="hover:text-red-500 hover:bg-red-50"
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateModal onClose={() => setShowCreate(false)} onSubmit={handleCreate} />
      )}
      {editingUser && (
        <EditModal user={editingUser} onClose={() => setEditingUser(null)} onSubmit={handleEdit} />
      )}
      {deleteConfirmId && (
        <ConfirmModal
          title="Benutzer löschen?"
          message={`„${deleteTarget?.display_name}" wird dauerhaft gelöscht und kann sich nicht mehr anmelden.`}
          confirmLabel="Löschen"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteConfirmId(null)}
        />
      )}
    </div>
  )
}

// ── Sub-components ──────────────────────────────────────────────

function Badge({ active, activeLabel, inactiveLabel, ActiveIcon, InactiveIcon, green }) {
  const Icon = active ? ActiveIcon : InactiveIcon
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
      active && green ? 'bg-[#eef4ee] text-[#5b7c5e]' : 'bg-[#f5f5f5] text-[#9a9a9a]'
    }`}>
      <Icon size={10} />
      {active ? activeLabel : inactiveLabel}
    </span>
  )
}

function IconButton({ icon, title, onClick, disabled = false, hoverClass }) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`p-1.5 rounded-lg text-[#c0cfc1] transition-colors ${hoverClass} disabled:opacity-25 disabled:cursor-not-allowed`}
    >
      {icon}
    </button>
  )
}

function ErrorBanner({ message, onDismiss }) {
  return (
    <div className="mb-5 flex items-start gap-2 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      <span className="mt-px">⚠️</span>
      <span className="flex-1">{message}</span>
      <button onClick={onDismiss} className="text-red-400 hover:text-red-600"><X size={14} /></button>
    </div>
  )
}

// ── Modals ──────────────────────────────────────────────────────

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30">
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-md"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#f0f4f0]">
          <h2 className="font-serif text-xl text-[#2d3b2e]">{title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#a8baa9] hover:text-[#5b7c5e] hover:bg-[#eef4ee] transition-colors"
          >
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function CreateModal({ onClose, onSubmit }) {
  const [form, setForm] = useState({ username: '', display_name: '', password: '', email: '', is_admin: false })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onSubmit({ ...form, email: form.email || null })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Neuer Benutzer" onClose={onClose}>
      <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
        {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
        <Field label="Anzeigename" required>
          <Input value={form.display_name} onChange={set('display_name')} placeholder="Max Mustermann" required />
        </Field>
        <Field label="Benutzername" required>
          <Input value={form.username} onChange={set('username')} placeholder="max" required autoComplete="off" />
        </Field>
        <Field label="Passwort" required>
          <Input type="password" value={form.password} onChange={set('password')} placeholder="••••••••" required autoComplete="new-password" />
        </Field>
        <Field label="E-Mail (optional)">
          <Input type="email" value={form.email} onChange={set('email')} placeholder="max@beispiel.de" />
        </Field>
        <label className="flex items-center gap-3 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={form.is_admin}
            onChange={set('is_admin')}
            className="w-4 h-4 rounded border-[#d4e2d5] text-[#5b7c5e] accent-[#5b7c5e]"
          />
          <span className="text-sm text-[#3d4f3e]">Admin-Rechte</span>
        </label>
        <div className="flex gap-3 pt-2">
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-[#d4e2d5] text-sm text-[#6b7c6c] hover:bg-[#f5f8f5] transition-colors">
            Abbrechen
          </button>
          <button type="submit" disabled={loading} className="flex-1 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors">
            {loading ? 'Erstellen…' : 'Erstellen'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function EditModal({ user, onClose, onSubmit }) {
  const [form, setForm] = useState({
    display_name: user.display_name,
    email: user.email ?? '',
    is_active: user.is_active,
    is_admin: user.is_admin,
  })
  const [moduleKeys, setModuleKeys] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getUserModules(user.id)
      .then(setModuleKeys)
      .catch(() => {})
  }, [user.id])

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  function toggleModule(key) {
    setModuleKeys(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onSubmit({ ...form, email: form.email || null }, moduleKeys)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title={`${user.display_name} bearbeiten`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
        {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
        <Field label="Anzeigename" required>
          <Input value={form.display_name} onChange={set('display_name')} required />
        </Field>
        <Field label="E-Mail">
          <Input type="email" value={form.email} onChange={set('email')} placeholder="optional" />
        </Field>
        <div className="space-y-2.5">
          <Toggle label="Aktiv" checked={form.is_active} onChange={set('is_active')} />
          <Toggle label="Admin-Rechte" checked={form.is_admin} onChange={set('is_admin')} />
        </div>
        <div>
          <p className="text-sm font-medium text-[#3d4f3e] mb-2">Module</p>
          <div className="space-y-2 rounded-xl border border-[#e4ede4] p-3">
            {ALL_MODULES.map(mod => (
              <label key={mod.key} className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={moduleKeys.includes(mod.key)}
                  onChange={() => toggleModule(mod.key)}
                  className="w-4 h-4 rounded border-[#d4e2d5] accent-[#5b7c5e]"
                />
                <span className="text-sm text-[#3d4f3e]">{mod.emoji} {mod.name}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="flex gap-3 pt-2">
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl border border-[#d4e2d5] text-sm text-[#6b7c6c] hover:bg-[#f5f8f5] transition-colors">
            Abbrechen
          </button>
          <button type="submit" disabled={loading} className="flex-1 py-2.5 rounded-xl bg-[#5b7c5e] text-white text-sm font-medium hover:bg-[#4a6b4d] disabled:opacity-60 transition-colors">
            {loading ? 'Speichern…' : 'Speichern'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ConfirmModal({ title, message, confirmLabel, danger, onConfirm, onCancel }) {
  const [loading, setLoading] = useState(false)

  async function handleConfirm() {
    setLoading(true)
    try { await onConfirm() } finally { setLoading(false) }
  }

  return (
    <Modal title={title} onClose={onCancel}>
      <div className="px-6 py-5">
        <p className="text-sm text-[#6b7c6c] mb-6">{message}</p>
        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 py-2.5 rounded-xl border border-[#d4e2d5] text-sm text-[#6b7c6c] hover:bg-[#f5f8f5] transition-colors">
            Abbrechen
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className={`flex-1 py-2.5 rounded-xl text-sm font-medium text-white disabled:opacity-60 transition-colors ${
              danger ? 'bg-red-500 hover:bg-red-600' : 'bg-[#5b7c5e] hover:bg-[#4a6b4d]'
            }`}
          >
            {loading ? `${confirmLabel}…` : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}

// ── Primitives ──────────────────────────────────────────────────

function Field({ label, required, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-[#3d4f3e] mb-1.5">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}

function Input({ ...props }) {
  return (
    <input
      {...props}
      className="w-full px-4 py-2.5 rounded-xl border border-[#d4e2d5] bg-[#faf8f4] text-[#2d3b2e] placeholder-[#b0c4b1] text-sm outline-none focus:border-[#5b7c5e] focus:ring-2 focus:ring-[#5b7c5e]/20 transition-all"
    />
  )
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="w-4 h-4 rounded border-[#d4e2d5] accent-[#5b7c5e]"
      />
      <span className="text-sm text-[#3d4f3e]">{label}</span>
    </label>
  )
}
